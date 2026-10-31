"""Metrics compile from metrics.yml and agree with each other."""
import pytest

from c360 import semantic

NAMES = list(semantic.metrics())


def test_twelve_metrics_defined():
    assert len(NAMES) == 12


@pytest.mark.parametrize("name", NAMES)
def test_metric_compiles_and_runs(wh, name):
    rows = semantic.query(name, by=["tenant_id"])
    assert len(rows) == 3
    assert all(r["value"] is not None for r in rows)


@pytest.mark.parametrize("name", [n for n, m in semantic.metrics().items() if m["type"] == "ratio"])
def test_ratio_is_ratio_of_sums(wh, name):
    """The all tenant rate must equal total numerator over total denominator, not an average of rates."""
    total = semantic.query(name)[0]
    per = semantic.query(name, by=["tenant_id"])
    num = sum(float(r["numerator"]) for r in per)
    den = sum(float(r["denominator"]) for r in per)
    assert float(total["value"]) == pytest.approx(num / den)


def test_counts_add_up_across_months(wh):
    total = semantic.query("leads_received")[0]["value"]
    by_month = semantic.query("leads_received", by=["month"])
    assert sum(int(r["value"]) for r in by_month) == int(total)


def test_unknown_dimension_is_rejected():
    with pytest.raises(ValueError):
        semantic.compile_sql("leads_received", by=["customer_phone"])


def test_compiled_files_match_definitions(wh):
    from c360 import config
    for name in NAMES:
        on_disk = (config.SEMANTIC / "compiled" / f"{name}.sql").read_text().strip()
        assert on_disk == semantic.compile_sql(name, by=["tenant_id", "month"]).strip()
