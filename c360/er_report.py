"""Score entity resolution against the hidden ground truth.

Pairwise precision: of all record pairs we put in the same customer, the share
that really are the same person. Pairwise recall: of all record pairs that
really are the same person, the share we put together. Scored inside each tenant.
"""
from __future__ import annotations

import json

from . import config, er
from .warehouse import get_session, q

ABLATIONS = [
    ("exact phone only", ["phone"]),
    ("phone + email", ["phone", "email"]),
    ("+ system ids (ServiceTitan id, job number, lead id)",
     ["phone", "email", "st_customer_id", "external_lead_id", "invoice_job"]),
    ("+ fuzzy name and address (full)", er.DEFAULT_RULES),
]


def load_truth():
    s = get_session()
    s.query(f"""CREATE OR REPLACE TABLE er.truth ENGINE = MergeTree ORDER BY record_key AS
        SELECT concat(tenant_id, '|', source, ':', record_id) AS record_key, tenant_id, source, person_id
        FROM file('{config.TRUTH / 'identity_truth.csv'}', 'CSVWithNames',
                  'tenant_id String, source String, record_id String, person_id String')""")


def score(table: str = "er.identity_map", key: str = "customer_key") -> dict:
    sql = f"""
    WITH j AS (
        SELECT t.tenant_id AS tenant_id, t.person_id AS person_id, p.{key} AS cluster
        FROM er.truth AS t INNER JOIN {table} AS p ON p.record_key = t.record_key
    ),
    pred AS (SELECT sum(n * (n - 1) / 2) AS v FROM (SELECT count() AS n FROM j GROUP BY tenant_id, cluster)),
    tru AS (SELECT sum(n * (n - 1) / 2) AS v FROM (SELECT count() AS n FROM j GROUP BY tenant_id, person_id)),
    tp AS (SELECT sum(n * (n - 1) / 2) AS v FROM (SELECT count() AS n FROM j GROUP BY tenant_id, cluster, person_id))
    SELECT (SELECT v FROM tp) AS tp, (SELECT v FROM pred) AS pred_pairs, (SELECT v FROM tru) AS true_pairs,
           (SELECT count() FROM j) AS records,
           (SELECT uniqExact(tenant_id, person_id) FROM j) AS true_people,
           (SELECT uniqExact(tenant_id, cluster) FROM j) AS predicted_customers,
           (SELECT countIf(c = 1) FROM (SELECT uniqExact(cluster) AS c FROM j GROUP BY tenant_id, person_id)) AS people_in_one_customer,
           (SELECT countIf(c > 1) FROM (SELECT uniqExact(person_id) AS c FROM j GROUP BY tenant_id, cluster)) AS customers_mixing_people
    """
    r = q(sql)[0]
    tp, pp, tr = float(r["tp"]), float(r["pred_pairs"]), float(r["true_pairs"])
    precision = tp / pp if pp else 1.0
    recall = tp / tr if tr else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4),
            "records": int(r["records"]), "true_people": int(r["true_people"]),
            "predicted_customers": int(r["predicted_customers"]),
            "people_fully_resolved_pct": round(100 * int(r["people_in_one_customer"]) / int(r["true_people"]), 2),
            "customers_mixing_people": int(r["customers_mixing_people"]),
            "pairs": {"true_positive": int(tp), "predicted": int(pp), "true": int(tr)}}


def cross_tenant_leaks() -> int:
    """Customer keys that appear in more than one tenant. Must be 0."""
    return int(q("SELECT count() AS n FROM (SELECT customer_key FROM er.identity_map GROUP BY customer_key HAVING uniqExact(tenant_id) > 1)")[0]["n"])


def run() -> dict:
    s = get_session()
    load_truth()
    final = score()
    final["cross_tenant_key_leaks"] = cross_tenant_leaks()
    per_tenant = {}
    for t in config.TENANTS:
        tid = t["tenant_id"]
        s.query(f"""CREATE OR REPLACE VIEW er._map_one AS SELECT * FROM er.identity_map WHERE tenant_id = '{tid}'""")
        per_tenant[tid] = score("er._map_one")
    ablation = []
    for label, rules in ABLATIONS:
        er.build_edges(s, rules)
        er.connected_components(s)
        res = score("er._labels", "label")
        ablation.append({"rules": label, **{k: res[k] for k in ("precision", "recall", "f1", "predicted_customers")}})
    er.build_edges(s, er.DEFAULT_RULES)   # leave the full edge set in place
    er.connected_components(s)
    rule_counts = q("SELECT rule, count() AS edges FROM er.edges GROUP BY rule ORDER BY rule")
    out = {"final": final, "per_tenant": per_tenant, "ablation": ablation, "edges_by_rule": rule_counts}
    config.REPORTS.mkdir(exist_ok=True)
    (config.REPORTS / "entity_resolution.json").write_text(json.dumps(out, indent=2))
    return out


def main():
    from .warehouse import build
    if not (config.WAREHOUSE / "marts").exists():
        build()
    print(json.dumps(run(), indent=2))


if __name__ == "__main__":
    main()
