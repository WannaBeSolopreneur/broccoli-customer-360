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
}


def test_ten_sample_questions():
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
