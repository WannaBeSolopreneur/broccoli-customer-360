"""Entity resolution: link source records into one customer per tenant.

Step 1. Build match edges with SQL rules (exact and fuzzy). Every rule only
        compares records inside the same tenant.
Step 2. Find connected groups with label propagation in ClickHouse.
Step 3. Give each group a customer_key. Keys are kept in a small registry so a
        customer keeps the same key on the next build, even if new records join.
"""
from __future__ import annotations

import csv
import hashlib
from pathlib import Path

# Each rule returns rows (tenant_id, a, b, rule). a and b are record keys.
RULES: dict[str, str] = {
    # A phone used by people with different first initials is a household
    # phone (a shared landline). There, records only match when the first
    # initial agrees. Records with no name join the most common initial.
    "phone": """
        WITH ph AS (
            SELECT tenant_id, phone_e164,
                   uniqExactIf(substring(first_name, 1, 1), first_name != '') AS initials,
                   topKIf(1)(substring(first_name, 1, 1), first_name != '')[1] AS top_initial
            FROM er.identity_records WHERE phone_e164 IS NOT NULL
            GROUP BY tenant_id, phone_e164
        )
        SELECT r.tenant_id AS tenant_id, r.record_key AS a,
               min(r.record_key) OVER (PARTITION BY r.tenant_id, r.phone_e164,
                   if(p.initials > 1, if(r.first_name = '', p.top_initial, substring(r.first_name, 1, 1)), '')) AS b,
               'phone' AS rule
        FROM er.identity_records AS r
        INNER JOIN ph AS p ON p.tenant_id = r.tenant_id AND p.phone_e164 = r.phone_e164""",
    "email": """
        SELECT tenant_id, record_key, min(record_key) OVER (PARTITION BY tenant_id, email), 'email'
        FROM er.identity_records WHERE email IS NOT NULL""",
    "st_customer_id": """
        SELECT tenant_id, record_key, min(record_key) OVER (PARTITION BY tenant_id, st_customer_id), 'st_customer_id'
        FROM er.identity_records WHERE source = 'jobs' AND st_customer_id IS NOT NULL""",
    "external_lead_id": """
        SELECT tenant_id, record_key, min(record_key) OVER (PARTITION BY tenant_id, external_lead_id), 'external_lead_id'
        FROM er.identity_records WHERE source = 'leads' AND external_lead_id IS NOT NULL""",
    "invoice_job": """
        SELECT i.tenant_id, i.record_key, j.record_key, 'invoice_job'
        FROM er.identity_records AS i
        INNER JOIN er.identity_records AS j ON i.tenant_id = j.tenant_id AND i.job_number = j.job_number
        WHERE i.source = 'invoices' AND j.source = 'jobs' AND i.job_number IS NOT NULL""",
    # Fuzzy step. Same house number, similar street, compatible zip, and a
    # similar name. Nicknames were already mapped (Bob to Robert) upstream.
    "fuzzy_name_address": """
        SELECT x.tenant_id, x.record_key, y.record_key, 'fuzzy_name_address'
        FROM er.identity_records AS x
        INNER JOIN er.identity_records AS y ON x.tenant_id = y.tenant_id AND x.house_number = y.house_number
        WHERE x.record_key < y.record_key
          AND x.street_key IS NOT NULL AND y.street_key IS NOT NULL
          AND x.last_name IS NOT NULL AND y.last_name IS NOT NULL
          AND x.first_name != '' AND y.first_name != ''
          AND (x.zip5 IS NULL OR y.zip5 IS NULL OR x.zip5 = y.zip5)
          AND ngramDistance(x.street_key, y.street_key) <= 0.35
          AND jaroWinklerSimilarity(x.last_name, y.last_name) >= 0.92
          AND (jaroWinklerSimilarity(x.first_name, y.first_name) >= 0.90
               OR ((length(x.first_name) = 1 OR length(y.first_name) = 1)
                   AND substring(x.first_name, 1, 1) = substring(y.first_name, 1, 1)))""",
}
DEFAULT_RULES = list(RULES)


def build_edges(s, rules: list[str] | None = None) -> None:
    rules = rules or DEFAULT_RULES
    union = "\nUNION ALL\n".join(f"SELECT * FROM ({RULES[r]})" for r in rules)
    s.query(f"""CREATE OR REPLACE TABLE er.edges ENGINE = MergeTree ORDER BY (tenant_id, a) AS
        SELECT tenant_id, a, b, rule FROM ({union}) WHERE a != b""")


def connected_components(s, max_iter: int = 50) -> int:
    """Label propagation. Each record takes the smallest label among itself and
    its neighbours, until nothing changes. Returns the number of rounds."""
    s.query("""CREATE OR REPLACE TABLE er._labels ENGINE = MergeTree ORDER BY record_key AS
               SELECT tenant_id, record_key, record_key AS label FROM er.identity_records""")
    s.query("""CREATE OR REPLACE TABLE er._undirected ENGINE = MergeTree ORDER BY a AS
               SELECT a, b FROM er.edges UNION ALL SELECT b, a FROM er.edges""")
    for i in range(1, max_iter + 1):
        s.query("""CREATE OR REPLACE TABLE er._labels_next ENGINE = MergeTree ORDER BY record_key AS
            SELECT x.tenant_id AS tenant_id, x.record_key AS record_key,
                   if(m.min_nb IS NOT NULL AND m.min_nb < x.label, m.min_nb, x.label) AS label
            FROM er._labels AS x
            LEFT JOIN (
                SELECT e.a AS node, min(l.label) AS min_nb
                FROM er._undirected AS e INNER JOIN er._labels AS l ON l.record_key = e.b
                GROUP BY e.a
            ) AS m ON m.node = x.record_key""")
        changed = int(s.query("""SELECT count() FROM er._labels AS x
            INNER JOIN er._labels_next AS y ON x.record_key = y.record_key WHERE x.label != y.label""", "CSV").bytes().decode().strip())
        s.query("EXCHANGE TABLES er._labels AND er._labels_next")
        if changed == 0:
            return i
    raise RuntimeError("label propagation did not converge")


def _new_key(tenant_id: str, anchor: str) -> str:
    return "cus_" + hashlib.sha1(f"{tenant_id}|{anchor}".encode()).hexdigest()[:16]


def assign_keys(s, registry_path: Path, tmp_dir: Path) -> dict:
    """Turn cluster labels into stable customer keys and save the registry."""
    out = s.query("SELECT tenant_id, record_key, label FROM er._labels ORDER BY record_key", "CSV").bytes().decode()
    rows = list(csv.reader(out.splitlines()))
    registry: dict[str, str] = {}
    if registry_path.exists():
        with open(registry_path) as fh:
            for r in csv.DictReader(fh):
                registry[r["record_key"]] = r["customer_key"]
    clusters: dict[str, list[tuple[str, str]]] = {}
    for tenant_id, record_key, label in rows:
        clusters.setdefault(label, []).append((tenant_id, record_key))

    used: set[str] = set()
    taken: set[str] = set(registry.values())
    mapping: dict[str, tuple[str, str]] = {}
    stats = {"clusters": len(clusters), "reused_keys": 0, "new_keys": 0, "merged_keys": 0}
    merges: list[tuple[str, str]] = []
    for label in sorted(clusters):
        members = clusters[label]
        tenant_id = members[0][0]
        prior = sorted({registry[rk] for _, rk in members if rk in registry} - used)
        if prior:
            key = prior[0]
            stats["reused_keys"] += 1
            for old in prior[1:]:
                merges.append((old, key))
                stats["merged_keys"] += 1
        else:
            anchor = min(rk for _, rk in members)
            key, salt = _new_key(tenant_id, anchor), 0
            # Never hand out a key that another customer already has or had.
            while key in used or key in taken:
                salt += 1
                key = _new_key(tenant_id, f"{anchor}#{salt}")
            stats["new_keys"] += 1
        used.add(key)
        for t, rk in members:
            mapping[rk] = (t, key)

    registry_path.parent.mkdir(parents=True, exist_ok=True)
    with open(registry_path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["record_key", "customer_key"])
        for rk in sorted(set(registry) | set(mapping)):
            w.writerow([rk, mapping[rk][1] if rk in mapping else registry[rk]])

    tmp_dir.mkdir(parents=True, exist_ok=True)
    map_csv = tmp_dir / "identity_map.csv"
    with open(map_csv, "w", newline="") as fh:
        w = csv.writer(fh)
        for rk, (t, key) in mapping.items():
            w.writerow([t, rk, key])
    s.query(f"""CREATE OR REPLACE TABLE er.identity_map ENGINE = MergeTree ORDER BY (tenant_id, record_key) AS
        SELECT r.tenant_id AS tenant_id, r.record_key AS record_key, r.source AS source, r.record_id AS record_id,
               m.customer_key AS customer_key
        FROM er.identity_records AS r
        INNER JOIN file('{map_csv}', 'CSV', 'tenant_id String, record_key String, customer_key String') AS m
            ON m.record_key = r.record_key""")
    merges_csv = tmp_dir / "key_merges.csv"
    with open(merges_csv, "w", newline="") as fh:
        csv.writer(fh).writerows(merges or [["", ""]])
    s.query(f"""CREATE OR REPLACE TABLE er.key_merges ENGINE = MergeTree ORDER BY old_key AS
        SELECT * FROM file('{merges_csv}', 'CSV', 'old_key String, new_key String') WHERE old_key != ''""")
    return stats


def resolve(s, registry_path: Path, tmp_dir: Path, rules: list[str] | None = None) -> dict:
    build_edges(s, rules)
    rounds = connected_components(s)
    stats = assign_keys(s, registry_path, tmp_dir)
    stats["rounds"] = rounds
    return stats
