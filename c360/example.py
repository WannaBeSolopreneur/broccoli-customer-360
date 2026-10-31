"""Show one messy customer: every raw record that entity resolution joined into one customer_key.

Picks a customer seen in all five sources, with at least three spellings of the
name and three phone formats. The hidden ground truth confirms it is one person.
"""
from __future__ import annotations

import json
import sys

from . import config, er_report
from .warehouse import q

RAW_FIELDS = {
    "calls": ("call_id", "caller_name", "customer_phone", "''", "''"),
    "jobs": ("job_id", "customer_name", "customer_phone", "customer_email", "location_street"),
    "invoices": ("invoice_id", "bill_to_name", "bill_to_phone", "bill_to_email", "bill_to_address"),
    "tickets": ("ticket_id", "requester_name", "requester_phone", "requester_email", "''"),
}


def pick(tenant_id: str = "tnt_alpine") -> str:
    rows = q(f"""
        WITH c AS (
            SELECT m.customer_key AS customer_key, uniqExact(m.source) AS n_sources,
                   uniqExact(r.first_token) AS n_first, count() AS n_records,
                   uniqExact(t.person_id) AS n_people
            FROM er.identity_map AS m
            INNER JOIN er.identity_records AS r ON r.record_key = m.record_key
            INNER JOIN er.truth AS t ON t.record_key = m.record_key
            WHERE m.tenant_id = '{tenant_id}'
            GROUP BY m.customer_key
        )
        SELECT customer_key FROM c
        WHERE n_sources = 5 AND n_people = 1 AND n_first >= 3 AND n_records BETWEEN 7 AND 12
        ORDER BY n_first DESC, n_records DESC, customer_key LIMIT 1""")
    return rows[0]["customer_key"]


def records(customer_key: str) -> list[dict]:
    out = []
    keys = q(f"SELECT tenant_id, source, record_id FROM er.identity_map WHERE customer_key = '{customer_key}' ORDER BY source, record_id")
    for k in keys:
        src, rid, tid = k["source"], k["record_id"], k["tenant_id"]
        if src == "leads":
            r = q(f"SELECT payload FROM raw.leads WHERE tenant_id = '{tid}' AND lead_row_id = '{rid}'")[0]
            p = json.loads(r["payload"])
            c = p.get("customer", {})
            name = c.get("name") or f"{c.get('firstName', '')} {c.get('lastName', '')}".strip()
            addr = p.get("address", "")
            addr = addr.get("street", "") if isinstance(addr, dict) else addr.split(",")[0]
            out.append({"source": src, "name": name, "phone": c.get("phone", ""), "email": c.get("email", ""),
                        "street": addr})
            continue
        idc, name, phone, email, street = RAW_FIELDS[src]
        r = q(f"SELECT {name} AS name, {phone} AS phone, {email} AS email, {street} AS street "
              f"FROM raw.{src} WHERE tenant_id = '{tid}' AND {idc} = '{rid}'")[0]
        r["street"] = r["street"].split(",")[0]
        out.append({"source": src, **r})
    return out


def main():
    er_report.load_truth()
    tenant = sys.argv[1] if len(sys.argv) > 1 else "tnt_alpine"
    key = pick(tenant)
    recs = records(key)
    dc = q(f"SELECT display_name, primary_phone, primary_email, street_key FROM marts.dim_customer WHERE customer_key = '{key}'")[0]
    print(f"{len(recs)} raw records, {len({r['source'] for r in recs})} sources, ground truth: 1 person")
    for r in recs:
        print(f"  {r['source']:9s} {r['name'][:24]:24s} {r['phone'][:16]:16s} {r['email'][:34]:34s} {r['street'][:30]}")
    print(f"one customer: {key}  {dc['display_name']}  {dc['primary_phone']}  {dc['primary_email']}")
    (config.REPORTS / "example_customer.json").write_text(json.dumps(
        {"customer_key": key, "records": recs, "dim_customer": dc}, indent=2))


if __name__ == "__main__":
    main()
