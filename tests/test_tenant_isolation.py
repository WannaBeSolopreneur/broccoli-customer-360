"""A tenant can only ever see its own rows."""
import pytest

from c360 import config, semantic

TENANTS = [t["tenant_id"] for t in config.TENANTS]
TABLES = ["dim_customer", "fct_calls", "fct_leads", "fct_jobs", "fct_invoices", "fct_tickets", "fct_memberships"]


def test_every_mart_has_tenant_id(wh):
    for t in TABLES:
        cols = {r["name"] for r in wh.q(f"DESCRIBE TABLE marts.{t}")}
        assert "tenant_id" in cols, t


@pytest.mark.parametrize("table", TABLES)
def test_tenant_views_return_only_own_rows(wh, table):
    for tid in TENANTS:
        seen = wh.q(f"SELECT tenant_id, count() AS n FROM tenant_api.{table}(tenant_id='{tid}') GROUP BY tenant_id")
        assert [r["tenant_id"] for r in seen] == [tid]
        total = wh.scalar(f"SELECT count() FROM marts.{table} WHERE tenant_id = '{tid}'")
        assert int(seen[0]["n"]) == int(total)


def test_unknown_tenant_sees_nothing(wh):
    assert int(wh.scalar("SELECT count() FROM tenant_api.fct_leads(tenant_id='tnt_nobody')")) == 0


def test_injection_attempt_sees_nothing(wh):
    sneaky = "tnt_alpine'' OR 1=1 --"
    assert int(wh.scalar(f"SELECT count() FROM tenant_api.fct_leads(tenant_id='{sneaky}')")) == 0


def test_metric_views_are_tenant_scoped(wh):
    for name in semantic.metrics():
        rows = wh.q(f"SELECT DISTINCT tenant_id FROM tenant_api.metric_{name}(tenant_id='tnt_bayside')")
        assert [r["tenant_id"] for r in rows] in ([], ["tnt_bayside"])


def test_compiler_rejects_unsafe_tenant(wh):
    with pytest.raises(ValueError):
        semantic.compile_sql("leads_received", tenant_id="x' OR '1'='1")


def test_benchmarks_have_no_tenant_column(wh):
    cols = {r["name"] for r in wh.q("DESCRIBE TABLE benchmarks.metric_benchmarks")}
    assert "tenant_id" not in cols
    assert cols == {"metric", "n_tenants", "average", "p25", "median", "p75"}


def test_benchmark_bands_hidden_under_five_tenants(wh):
    """With 3 tenants the median would be one tenant's exact value, so only the average shows."""
    rows = wh.q("SELECT * FROM benchmarks.metric_benchmarks")
    assert rows, "benchmarks should show with 3 tenants"
    for r in rows:
        assert int(r["n_tenants"]) == 3
        assert r["p25"] is None and r["median"] is None and r["p75"] is None
        assert r["average"] is not None


def test_benchmark_average_is_not_any_single_tenant(wh):
    for r in wh.q("SELECT metric, average FROM benchmarks.metric_benchmarks"):
        own = [float(x["value"]) for x in semantic.query(r["metric"], by=["tenant_id"])]
        assert all(abs(float(r["average"]) - v) > 1e-9 for v in own)


def test_my_benchmarks_shows_own_value_only(wh):
    rows = wh.q("SELECT * FROM tenant_api.my_benchmarks(tenant_id='tnt_alpine')")
    cols = set(rows[0])
    assert "tenant_id" not in cols
    own = {r["metric"]: r["my_value"] for r in rows}
    direct = semantic.query("lead_to_booking_rate", tenant_id="tnt_alpine")[0]["value"]
    assert own["lead_to_booking_rate"] == pytest.approx(direct)


def test_row_policies_on_real_server(wh):
    """chDB cannot create users. This starts a temporary ClickHouse server if the binary exists."""
    from c360 import row_policies
    binary = row_policies.find_binary()
    if not binary:
        pytest.skip("set CLICKHOUSE_BIN to run the row policy test")
    r = row_policies.run(binary)
    assert r["all_ok"], [c for c in r["checks"] if not c["ok"]]
