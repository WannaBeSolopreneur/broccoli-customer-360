"""Plain English questions map to the right metric."""
import pytest

from c360 import ask

EXPECTED = {
    "What is our speed to lead at Alpine?": ("speed_to_lead_median_sec", "tnt_alpine", []),
    "Compare lead conversion for each contractor": ("lead_to_booking_rate", None, ["tenant_id"]),
    "How much booked revenue did Broccoli bring Bayside in July?": ("booked_revenue", "tnt_bayside", []),
    "What is the call answer rate at Lone Star?": ("call_answer_rate", "tnt_lonestar", []),
    "Membership renewal rate by tenant": ("membership_renewal_rate", None, ["tenant_id"]),
    "How many leads did Bayside get by lead source?": ("leads_received", "tnt_bayside", ["lead_source"]),
    "Show the call booking rate trend by month for Alpine": ("ai_call_booking_rate", "tnt_alpine", ["month"]),
    "What is revenue per customer for each contractor?": ("revenue_per_customer", None, ["tenant_id"]),
    "How long does it take to solve support tickets at Bayside?": ("ticket_resolution_median_hours", "tnt_bayside", []),
    "What share of invoices are paid at Lone Star?": ("invoice_collection_rate", "tnt_lonestar", []),
    "How much revenue did the AI book after hours at Desert Air?": ("after_hours_booked_revenue", "tnt_desert", []),
    "How many missed calls did Gulf Coast have?": ("missed_calls", "tnt_gulf", []),
    "Lead conversion by lead source at Alpine": ("lead_to_booking_rate", "tnt_alpine", ["lead_source"]),
    "How many repeat customers were found only by matching at Alpine?": ("repeat_customers_found_by_matching", "tnt_alpine", []),
    "How does Alpine compare to peer benchmarks?": ("peer_benchmarks", "tnt_alpine", []),
}


def test_fifteen_sample_questions():
    assert set(ask.SAMPLE_QUESTIONS) == set(EXPECTED)


@pytest.mark.parametrize("question", list(EXPECTED))
def test_question_maps_to_metric(wh, question):
    metric, tenant, by = EXPECTED[question]
    a = ask.answer(question)
    assert (a["metric"], a["tenant_id"], a["by"]) == (metric, tenant, by)
    assert a["rows"] and a["rows"][0]["value"] is not None


def test_month_filter(wh):
    a = ask.answer("How much booked revenue did Broccoli bring Bayside in July?")
    assert a["start"].startswith("2026-07-01") and a["end"].startswith("2026-08-01")


def test_every_tenant_name_is_understood():
    from c360 import config
    for t in config.TENANTS:
        name = t["name"].split(" (")[0]
        assert ask.find_tenant(f"what is the call answer rate at {name.lower()}") == t["tenant_id"]


def test_peer_benchmark_answer_shows_own_value_and_peers_only(wh):
    a = ask.answer("How does Alpine compare to peer benchmarks?")
    assert a["rows"]
    for r in a["rows"]:
        assert "tenant_id" not in r
        assert int(r["n_tenants"]) >= 5
        assert r["peer_median"] is not None
