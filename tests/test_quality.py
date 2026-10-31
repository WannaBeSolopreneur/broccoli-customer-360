"""Quality checks pass on good data and raise alerts on bad data."""
import copy

import yaml

from c360 import config, quality


def test_all_checks_pass(wh):
    res = quality.run()
    assert res["summary"]["errors"] == 0, res["alerts"]
    assert res["summary"]["total"] >= 50


def test_stale_feed_raises_alert(wh):
    spec = yaml.safe_load((config.MODELS / "schema.yml").read_text())
    later = "2026-10-02 06:00:00"  # one day with no new loads
    res = quality.freshness(spec, now=later)
    errors = {(r["table"], r["tenant_id"]) for r in res if r["status"] == "error"}
    assert ("raw.calls", "tnt_alpine") in errors
    quality.run()  # rewrite the normal report


def test_bad_rows_raise_alerts(wh):
    wh.get_session().query("CREATE DATABASE IF NOT EXISTS scratch")
    wh.get_session().query("CREATE OR REPLACE TABLE scratch.bad_leads ENGINE = Memory AS SELECT * FROM marts.fct_leads")
    wh.get_session().query("""INSERT INTO scratch.bad_leads (tenant_id, provider_id, external_lead_id, customer_key)
        SELECT 'tnt_unknown', provider_id, external_lead_id, 'cus_missing' FROM marts.fct_leads LIMIT 1""")
    spec = yaml.safe_load((config.MODELS / "schema.yml").read_text())
    t = copy.deepcopy(spec["tables"]["marts.fct_leads"])
    res = quality.column_tests({"tables": {"scratch.bad_leads": t}})
    failed = {r["check"] for r in res if r["failures"] > 0}
    assert "accepted_values(tenant_id)" in failed
    assert any(c.startswith("relationships(customer_key") for c in failed)
    wh.get_session().query("DROP TABLE scratch.bad_leads")


def test_docs_reach_clickhouse(wh):
    comment = wh.scalar("SELECT comment FROM system.tables WHERE database = 'marts' AND name = 'dim_customer'")
    assert "One row per resolved customer" in comment
