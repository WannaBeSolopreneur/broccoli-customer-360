"""Data quality: tests, freshness and reconciliation. Writes reports/quality.json.

Severity "error" fails the run (exit code 1). "warn" is reported only.
Alerts go to reports/alerts.json. In production the same list would be posted
to Slack or PagerDuty. Here nothing is sent anywhere.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime

import yaml

from . import config
from .warehouse import q


def _tenants() -> list[str]:
    return [t["tenant_id"] for t in config.TENANTS]


def _vals(v) -> list[str]:
    return _tenants() if v == "tenants" else [str(x) for x in v]


def column_tests(spec: dict) -> list[dict]:
    results = []
    for table, t in spec["tables"].items():
        for cols in t.get("unique", []):
            c = ", ".join(cols)
            bad = q(f"SELECT count() AS n FROM (SELECT {c} FROM {table} GROUP BY {c} HAVING count() > 1)")[0]["n"]
            results.append({"check": f"unique({c})", "table": table, "failures": int(bad), "severity": "error"})
        for col, cdef in (t.get("columns") or {}).items():
            for test in cdef.get("tests", []):
                if test == "not_null":
                    bad = q(f"SELECT countIf({col} IS NULL) AS n FROM {table}")[0]["n"]
                    results.append({"check": f"not_null({col})", "table": table, "failures": int(bad), "severity": "error"})
                elif isinstance(test, dict) and "accepted_values" in test:
                    vals = _vals(test["accepted_values"])
                    lst = ", ".join(f"'{v}'" for v in vals)
                    bad = q(f"SELECT countIf({col} IS NOT NULL AND {col} NOT IN ({lst})) AS n FROM {table}")[0]["n"]
                    results.append({"check": f"accepted_values({col})", "table": table, "failures": int(bad), "severity": "error"})
                elif isinstance(test, dict) and "relationships" in test:
                    parent = test["relationships"]
                    bad = q(f"""SELECT count() AS n FROM {table} AS c
                                LEFT ANTI JOIN {parent} AS p ON p.tenant_id = c.tenant_id AND p.{col} = c.{col}
                                WHERE c.{col} IS NOT NULL""")[0]["n"]
                    results.append({"check": f"relationships({col} -> {parent})", "table": table,
                                    "failures": int(bad), "severity": "error"})
    return results


def freshness(spec: dict, now: str = config.AS_OF) -> list[dict]:
    results = []
    for table, f in spec["freshness"].items():
        rows = q(f"""SELECT tenant_id, max(c360_ts({f['loaded_at']})) AS newest,
                            dateDiff('minute', max(c360_ts({f['loaded_at']})), toDateTime('{now}', 'UTC')) / 60.0 AS hours
                     FROM {table} GROUP BY tenant_id ORDER BY tenant_id""")
        seen = {r["tenant_id"] for r in rows}
        for tid in _tenants():
            if tid not in seen:
                results.append({"check": "freshness", "table": table, "tenant_id": tid, "hours_since_load": None,
                                "status": "error", "severity": "error", "failures": 1,
                                "detail": "no rows for this tenant"})
        for r in rows:
            h = float(r["hours"])
            status = "error" if h > f["error_after_hours"] else ("warn" if h > f["warn_after_hours"] else "pass")
            results.append({"check": "freshness", "table": table, "tenant_id": r["tenant_id"],
                            "hours_since_load": round(h, 2), "status": status,
                            "severity": status if status != "pass" else "error",
                            "failures": 0 if status == "pass" else 1})
    return results


def reconciliation() -> list[dict]:
    """Row counts must survive each layer. Nothing silently dropped or doubled."""
    checks = [
        ("raw.calls = marts.fct_calls", "SELECT (SELECT count() FROM raw.calls) - (SELECT count() FROM marts.fct_calls) AS n"),
        ("raw.jobs = marts.fct_jobs", "SELECT (SELECT count() FROM raw.jobs) - (SELECT count() FROM marts.fct_jobs) AS n"),
        ("raw.invoices = marts.fct_invoices", "SELECT (SELECT count() FROM raw.invoices) - (SELECT count() FROM marts.fct_invoices) AS n"),
        ("raw.tickets = marts.fct_tickets", "SELECT (SELECT count() FROM raw.tickets) - (SELECT count() FROM marts.fct_tickets) AS n"),
        ("unique lead ids = marts.fct_leads", """SELECT (SELECT uniqExact(tenant_id, JSONExtractString(payload, 'externalLeadId')) FROM raw.leads)
                                                 - (SELECT count() FROM marts.fct_leads) AS n"""),
        ("every identity record has a customer_key", "SELECT (SELECT count() FROM er.identity_records) - (SELECT count() FROM er.identity_map) AS n"),
        ("no customer_key spans two tenants", """SELECT count() AS n FROM (SELECT customer_key FROM er.identity_map
                                                  GROUP BY customer_key HAVING uniqExact(tenant_id) > 1)"""),
        ("non spam calls have a customer", "SELECT countIf(customer_key IS NULL AND NOT is_spam) AS n FROM marts.fct_calls"),
        ("no events after the as of time", f"""SELECT
            (SELECT countIf(started_at > toDateTime('{config.AS_OF}', 'UTC')) FROM marts.fct_calls)
          + (SELECT countIf(received_at > toDateTime('{config.AS_OF}', 'UTC')) FROM marts.fct_leads)
          + (SELECT countIf(created_on > toDateTime('{config.AS_OF}', 'UTC')) FROM marts.fct_jobs)
          + (SELECT countIf(invoice_date > toDateTime('{config.AS_OF}', 'UTC')) FROM marts.fct_invoices)
          + (SELECT countIf(created_at > toDateTime('{config.AS_OF}', 'UTC')) FROM marts.fct_tickets) AS n"""),
        ("revenue only on completed jobs", "SELECT countIf(status != 'Completed' AND total_revenue != 0) AS n FROM marts.fct_jobs"),
    ]
    out = []
    for name, sql in checks:
        n = int(q(sql)[0]["n"])
        out.append({"check": name, "table": "-", "failures": abs(n), "severity": "error"})
    return out


def run(now: str = config.AS_OF) -> dict:
    spec = yaml.safe_load((config.MODELS / "schema.yml").read_text())
    results = column_tests(spec) + freshness(spec, now) + reconciliation()
    for r in results:
        r.setdefault("status", "pass" if r["failures"] == 0 else r["severity"])
    alerts = [r for r in results if r["status"] != "pass"]
    summary = {"checked_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "as_of": now,
               "total": len(results), "passed": sum(r["status"] == "pass" for r in results),
               "warnings": sum(r["status"] == "warn" for r in results),
               "errors": sum(r["status"] == "error" for r in results)}
    config.REPORTS.mkdir(exist_ok=True)
    (config.REPORTS / "quality.json").write_text(json.dumps({"summary": summary, "results": results}, indent=2))
    (config.REPORTS / "alerts.json").write_text(json.dumps(alerts, indent=2))
    return {"summary": summary, "alerts": alerts}


def main():
    now = sys.argv[1] if len(sys.argv) > 1 else config.AS_OF
    res = run(now)
    s = res["summary"]
    print(f"quality checks: {s['total']} run, {s['passed']} passed, {s['warnings']} warnings, {s['errors']} errors")
    for a in res["alerts"]:
        print(f"  ALERT [{a['status']}] {a['check']} on {a['table']} {a.get('tenant_id', '')}".rstrip())
    sys.exit(1 if s["errors"] else 0)


if __name__ == "__main__":
    main()
