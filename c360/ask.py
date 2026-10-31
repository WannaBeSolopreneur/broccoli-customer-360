"""Ask a plain English question and get an answer from the metric layer.

This is keyword matching, not an LLM. The point is the contract: a question is
mapped to one metric in semantic/metrics.yml, and the SQL is compiled from that
definition. An AI agent would use the same contract (pick a metric, a tenant,
a time range, a breakdown) instead of writing its own SQL.
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass

from . import config, semantic

MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july",
                                       "august", "september", "october", "november", "december"], 1)}
TENANT_WORDS = {"alpine": "tnt_alpine", "bayside": "tnt_bayside", "lone star": "tnt_lonestar",
                "lonestar": "tnt_lonestar"}


@dataclass
class Plan:
    metric: str
    tenant_id: str | None
    start: str | None
    end: str | None
    by: list[str]
    score: int


def _words(s: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", s.lower()))


def plan(question: str) -> Plan:
    ql = question.lower()
    best, best_score = None, 0
    for name, m in semantic.metrics().items():
        score = 0
        for syn in m.get("synonyms", []) + [m["label"].lower(), name.replace("_", " ")]:
            if syn.lower() in ql:
                score = max(score, 10 + len(syn))
            else:
                overlap = len(_words(syn) & _words(ql))
                score = max(score, overlap * 2 if overlap == len(_words(syn)) else overlap)
        if score > best_score:
            best, best_score = name, score
    if best is None:
        raise ValueError("no metric matches this question")
    tenant = next((tid for w, tid in TENANT_WORDS.items() if w in ql), None)
    start = end = None
    for mname, num in MONTHS.items():
        if mname in ql:
            start = f"2026-{num:02d}-01 00:00:00"
            end = f"2026-{num + 1:02d}-01 00:00:00" if num < 12 else "2027-01-01 00:00:00"
    by = []
    if "by month" in ql or "per month" in ql or "each month" in ql or "trend" in ql:
        by.append("month")
    if tenant is None and ("each" in ql or "by tenant" in ql or "compare" in ql or "per contractor" in ql):
        by.insert(0, "tenant_id")
    for dim in semantic.metrics()[best].get("dimensions", []):
        if f"by {dim.replace('_', ' ')}" in ql or f"by {dim.split('_')[0]}" in ql:
            by.append(dim)
    return Plan(best, tenant, start, end, by, best_score)


def fmt(value, kind: str) -> str:
    if value is None:
        return "n/a"
    v = float(value)
    return {"percent": f"{v * 100:.1f}%", "currency": f"${v:,.0f}", "seconds": f"{v:,.0f} sec",
            "hours": f"{v:,.1f} h", "integer": f"{v:,.0f}"}.get(kind, f"{v:,.2f}")


def answer(question: str) -> dict:
    p = plan(question)
    m = semantic.metrics()[p.metric]
    sql = semantic.compile_sql(p.metric, by=p.by, tenant_id=p.tenant_id, start=p.start, end=p.end)
    rows = semantic.query(p.metric, by=p.by, tenant_id=p.tenant_id, start=p.start, end=p.end)
    return {"question": question, "metric": p.metric, "label": m["label"], "definition": m["description"],
            "tenant_id": p.tenant_id, "start": p.start, "end": p.end, "by": p.by, "sql": sql,
            "rows": [{**r, "display": fmt(r["value"], m["format"])} for r in rows]}


SAMPLE_QUESTIONS = [
    "What is our speed to lead at Alpine?",
    "Compare lead conversion for each contractor",
    "How much booked revenue did Broccoli bring Bayside in July?",
    "What is the call answer rate at Lone Star?",
    "Membership renewal rate by tenant",
    "How many leads did Bayside get by lead source?",
    "Show the call booking rate trend by month for Alpine",
    "What is revenue per customer for each contractor?",
    "How long does it take to solve support tickets at Bayside?",
    "What share of invoices are paid at Lone Star?",
]


def main():
    qs = sys.argv[1:] or SAMPLE_QUESTIONS
    for question in qs:
        a = answer(question)
        print(f"\nQ: {question}")
        print(f"   metric: {a['metric']}  |  {a['definition']}")
        for r in a["rows"][:8]:
            keys = [k for k in r if k not in ("value", "display", "numerator", "denominator", "rows_used")]
            label = ", ".join(str(r[k]) for k in keys) or (a["tenant_id"] or "all tenants")
            print(f"   {label}: {r['display']}")


if __name__ == "__main__":
    main()
