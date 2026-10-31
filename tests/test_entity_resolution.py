"""Entity resolution quality and key stability."""
from c360 import config, er, er_report


def test_precision_and_recall_floor(wh):
    s = er_report.score()
    # Floors, not targets. The real numbers are in reports/entity_resolution.json.
    assert s["precision"] >= 0.96
    assert s["recall"] >= 0.97


def test_rules_add_recall(wh):
    """Phone alone misses people. The full rule set finds more of them."""
    full = er_report.score()["recall"]
    s = wh.get_session()
    er.build_edges(s, ["phone"])
    er.connected_components(s)
    phone_only = er_report.score("er._labels", "label")["recall"]
    er.build_edges(s, None)
    er.connected_components(s)
    assert phone_only < full


def test_no_customer_spans_tenants(wh):
    assert er_report.cross_tenant_leaks() == 0


def test_keys_are_stable_on_rebuild(wh):
    before = {r["record_key"]: r["customer_key"] for r in wh.q("SELECT record_key, customer_key FROM er.identity_map")}
    er.resolve(wh.get_session(), config.ROOT / "warehouse" / "state" / "key_registry.csv",
               config.ROOT / "warehouse" / "tmp")
    after = {r["record_key"]: r["customer_key"] for r in wh.q("SELECT record_key, customer_key FROM er.identity_map")}
    assert before == after


def test_registry_keeps_old_key_when_clusters_merge(wh, tmp_path):
    """If two old customers turn out to be one person, the older key survives and the merge is logged."""
    s = wh.get_session()
    rows = wh.q("""SELECT label, groupArray(record_key) AS rks FROM er._labels
                   GROUP BY label HAVING count() >= 2 ORDER BY label LIMIT 1""")
    rks = rows[0]["rks"]
    reg = tmp_path / "registry.csv"
    reg.write_text("record_key,customer_key\n" + f"{rks[0]},cus_old_a\n" + f"{rks[1]},cus_old_b\n")
    stats = er.assign_keys(s, reg, tmp_path / "tmp")
    keys = {r["customer_key"] for r in wh.q(
        "SELECT customer_key FROM er.identity_map WHERE record_key IN ('" + "','".join(rks) + "')")}
    assert keys == {"cus_old_a"}
    assert stats["merged_keys"] == 1
    assert wh.q("SELECT old_key, new_key FROM er.key_merges") == [{"old_key": "cus_old_b", "new_key": "cus_old_a"}]
    # Put the real map back for the other tests.
    er.assign_keys(s, config.ROOT / "warehouse" / "state" / "key_registry.csv", config.ROOT / "warehouse" / "tmp")
