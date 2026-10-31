"""Semantic layer. Reads semantic/metrics.yml and compiles SQL.

Every consumer (dashboards, benchmarks, reports, the ask tool) calls
compile_sql() or query(). Nobody writes metric SQL by hand.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import yaml

from . import config

AGG = {
    "count": lambda m: "count()",
    "sum": lambda m: f"sum({m['expr']})",
    "avg": lambda m: f"avg({m['expr']})",
    "median": lambda m: f"quantileExact(0.5)({m['expr']})",
    "count_distinct": lambda m: f"uniqExact({m['expr']})",
    "ratio": lambda m: f"({m['numerator']}) / nullIf({m['denominator']}, 0)",
}
_SAFE = re.compile(r"^[A-Za-z0-9_\-: ]+$")


@lru_cache(maxsize=1)
def spec() -> dict:
    return yaml.safe_load((config.SEMANTIC / "metrics.yml").read_text())


def metrics() -> dict[str, dict]:
    return {m["name"]: m for m in spec()["metrics"]}


def compile_sql(name: str, by: list[str] | None = None, tenant_id: str | None = None,
                start: str | None = None, end: str | None = None) -> str:
    m = metrics()[name]
    by = by or []
    dims = []
    for d in by:
        if d in spec()["dimensions"]:
            dims.append((d, spec()["dimensions"][d]["sql"].format(time=m["time"])))
        elif d in m.get("dimensions", []):
            dims.append((d, d))
        else:
            raise ValueError(f"dimension {d!r} is not allowed for metric {name!r}")
    where = list(m.get("filters", []))
    for label, val in (("tenant_id", tenant_id), ("start", start), ("end", end)):
        if val is not None and not _SAFE.match(val):
            raise ValueError(f"unsafe value for {label}: {val!r}")
    if tenant_id is not None:
        where.append(f"tenant_id = '{tenant_id}'")
    if start:
        where.append(f"{m['time']} >= toDateTime('{start}', 'UTC')")
    if end:
        where.append(f"{m['time']} < toDateTime('{end}', 'UTC')")
    select = [f"{expr} AS {alias}" for alias, expr in dims]
    select.append(f"{AGG[m['type']](m)} AS value")
    if m["type"] == "ratio":
        select += [f"{m['numerator']} AS numerator", f"{m['denominator']} AS denominator"]
    select.append("count() AS rows_used")
    sql = f"-- metric: {name} ({m['label']})\nSELECT " + ",\n       ".join(select) + f"\nFROM {m['model']}"
    if where:
        sql += "\nWHERE " + "\n  AND ".join(f"({w})" for w in where)
    if dims:
        sql += "\nGROUP BY " + ", ".join(a for a, _ in dims) + "\nORDER BY " + ", ".join(a for a, _ in dims)
    return sql


def query(name: str, **kw) -> list[dict]:
    from .warehouse import q
    return q(compile_sql(name, **kw))


def benchmark_sql(peer_tenants: list[str] | None = None) -> str:
    """Peer benchmarks across tenants. Aggregates only, no tenant_id column.
    peer_tenants limits the peer group (for example one trade). A group smaller
    than benchmark_min_tenants returns no rows at all."""
    parts = []
    k = int(spec().get("benchmark_min_tenants", 5))
    band = int(spec().get("benchmark_min_tenants_for_band", 5))
    for t in peer_tenants or []:
        if not _SAFE.match(t):
            raise ValueError(f"unsafe tenant id: {t!r}")
    for name, m in metrics().items():
        if not m.get("benchmark"):
            continue
        inner = compile_sql(name, by=["tenant_id"])
        if peer_tenants is not None:
            inner = f"SELECT * FROM ({inner}) WHERE tenant_id IN (" + ", ".join(f"'{t}'" for t in peer_tenants) + ")"
        parts.append(f"""SELECT '{name}' AS metric, count() AS n_tenants,
       avg(value) AS average,
       if(count() >= {band}, quantileExactInclusive(0.25)(value), NULL) AS p25,
       if(count() >= {band}, quantileExactInclusive(0.5)(value), NULL) AS median,
       if(count() >= {band}, quantileExactInclusive(0.75)(value), NULL) AS p75
FROM ({inner}) HAVING n_tenants >= {k}""")
    return "\nUNION ALL\n".join(parts)


def create_views() -> int:
    """Create metrics.<name> views (tenant and month grain), tenant scoped
    metric views, and the cross tenant benchmark view."""
    from .warehouse import get_session
    s = get_session()
    s.query("CREATE DATABASE IF NOT EXISTS metrics")
    s.query("CREATE DATABASE IF NOT EXISTS benchmarks")
    out_dir = config.SEMANTIC / "compiled"
    out_dir.mkdir(exist_ok=True)
    n = 0
    for name in metrics():
        sql = compile_sql(name, by=["tenant_id", "month"])
        s.query(f"CREATE OR REPLACE VIEW metrics.{name} AS {sql}")
        s.query(f"CREATE OR REPLACE VIEW tenant_api.metric_{name} AS SELECT * FROM metrics.{name} "
                f"WHERE tenant_id = {{tenant_id:String}}")
        (out_dir / f"{name}.sql").write_text(sql + "\n")
        n += 1
    bsql = benchmark_sql()
    (out_dir / "_benchmarks.sql").write_text(bsql + "\n")
    # Benchmarks expose only aggregates across tenants. No tenant_id column.
    s.query(f"CREATE OR REPLACE VIEW benchmarks.metric_benchmarks AS {bsql}")
    own = "\nUNION ALL\n".join(
        f"SELECT '{name}' AS metric, value FROM ({compile_sql(name, by=['tenant_id'])}) WHERE tenant_id = {{tenant_id:String}}"
        for name, m in metrics().items() if m.get("benchmark"))
    s.query(f"""CREATE OR REPLACE VIEW tenant_api.my_benchmarks AS
        SELECT o.metric AS metric, o.value AS my_value, b.average AS peer_average, b.p25 AS peer_p25, b.median AS peer_median,
               b.p75 AS peer_p75, b.n_tenants AS n_tenants
        FROM ({own}) AS o INNER JOIN benchmarks.metric_benchmarks AS b ON b.metric = o.metric""")
    return n
