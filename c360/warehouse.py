"""Build the ClickHouse warehouse with chDB (embedded ClickHouse, no server).

Order: functions, raw, staging, identity records, entity resolution,
marts, tenant views, semantic metrics, benchmarks, column docs.
"""
from __future__ import annotations

import csv
import json
import shutil
import time
from pathlib import Path

import yaml
from chdb import session as chsession

from . import config, er

_SESSION = None


def get_session(path: Path = config.WAREHOUSE):
    """chDB allows one open session per process, so share it."""
    global _SESSION
    if _SESSION is None:
        path.mkdir(parents=True, exist_ok=True)
        _SESSION = chsession.Session(str(path))
        _SESSION.query("SET join_use_nulls = 1")
    return _SESSION


def q(sql: str, fmt: str = "JSONEachRow") -> list[dict]:
    """Run a query and return rows as dicts."""
    out = get_session().query(sql, fmt).bytes().decode()
    return [json.loads(line) for line in out.splitlines() if line.strip()]


def scalar(sql: str):
    rows = q(sql)
    return next(iter(rows[0].values())) if rows else None


def _template(sql: str) -> str:
    nick_from, nick_to = [], []
    with open(config.ROOT / "seeds" / "nicknames.csv") as fh:
        for r in csv.DictReader(fh):
            nick_from.append(r["nickname"])
            nick_to.append(r["formal"])
    arr = lambda xs: "[" + ", ".join(f"'{x}'" for x in xs) + "]"
    return (sql.replace("{{RAW}}", str(config.RAW))
               .replace("{{NICK_FROM}}", arr(nick_from))
               .replace("{{NICK_TO}}", arr(nick_to))
               .replace("{{AS_OF}}", config.AS_OF))


def statements(sql: str) -> list[str]:
    out, buf = [], []
    for line in sql.splitlines():
        buf.append(line)
        if line.rstrip().endswith(";"):
            stmt = "\n".join(buf).strip().rstrip(";")
            if any(l.strip() and not l.strip().startswith("--") for l in stmt.splitlines()):
                out.append(stmt)
            buf = []
    tail = "\n".join(buf).strip()
    if any(l.strip() and not l.strip().startswith("--") for l in tail.splitlines()):
        out.append(tail)
    return out


def run_file(path: Path) -> int:
    s = get_session()
    stmts = statements(_template(path.read_text()))
    for st in stmts:
        try:
            s.query(st)
        except Exception as e:  # make the failing model easy to find
            raise RuntimeError(f"{path.relative_to(config.ROOT)} failed: {e}\n---\n{st[:400]}") from e
    return len(stmts)


def apply_docs() -> int:
    """Copy column descriptions from models/schema.yml into ClickHouse comments,
    so people and AI tools see the same docs inside the warehouse."""
    spec = yaml.safe_load((config.MODELS / "schema.yml").read_text())
    s = get_session()
    n = 0
    for table, t in spec["tables"].items():
        if t.get("description"):
            s.query(f"ALTER TABLE {table} MODIFY COMMENT '{_esc(t['description'])}'")
        for col, c in (t.get("columns") or {}).items():
            if c.get("description"):
                s.query(f"ALTER TABLE {table} COMMENT COLUMN `{col}` '{_esc(c['description'])}'")
                n += 1
    return n


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace("'", "\\'").strip()


def build(fresh: bool = True, er_rules: list[str] | None = None) -> dict:
    from . import semantic  # local import keeps module load light

    timings: dict[str, float] = {}
    t0 = time.perf_counter()
    if fresh and _SESSION is None and config.WAREHOUSE.exists():
        shutil.rmtree(config.WAREHOUSE)
    get_session()

    def step(name, fn):
        t = time.perf_counter()
        res = fn()
        timings[name] = round(time.perf_counter() - t, 3)
        return res

    step("functions", lambda: run_file(config.MODELS / "00_functions.sql"))
    step("raw", lambda: run_file(config.MODELS / "raw" / "01_raw.sql"))
    step("staging", lambda: run_file(config.MODELS / "staging" / "01_staging.sql"))
    step("identity_records", lambda: run_file(config.MODELS / "intermediate" / "01_identity_records.sql"))
    er_stats = step("entity_resolution", lambda: er.resolve(
        get_session(), config.ROOT / "warehouse" / "state" / "key_registry.csv",
        config.ROOT / "warehouse" / "tmp", er_rules))
    step("marts", lambda: run_file(config.MODELS / "marts" / "01_marts.sql"))
    step("tenant_api", lambda: run_file(config.MODELS / "security" / "01_tenant_api.sql"))
    n_metrics = step("semantic", semantic.create_views)
    step("docs", apply_docs)
    timings["total"] = round(time.perf_counter() - t0, 3)
    counts = {t: scalar(f"SELECT count() FROM {t}") for t in
              ["raw.calls", "raw.leads", "raw.jobs", "raw.invoices", "raw.tickets",
               "er.identity_records", "er.edges", "marts.dim_customer", "marts.fct_calls",
               "marts.fct_leads", "marts.fct_jobs", "marts.fct_invoices", "marts.fct_tickets",
               "marts.fct_memberships"]}
    result = {"timings_sec": timings, "row_counts": counts, "entity_resolution": er_stats,
              "metric_views": n_metrics}
    config.REPORTS.mkdir(exist_ok=True)
    (config.REPORTS / "build.json").write_text(json.dumps(result, indent=2, default=str))
    return result


def main():
    res = build()
    print(json.dumps(res, indent=2, default=str))


if __name__ == "__main__":
    main()
