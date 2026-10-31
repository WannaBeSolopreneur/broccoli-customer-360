"""Shared paths and run settings."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = DATA / "raw"
TRUTH = DATA / "ground_truth"
WAREHOUSE = ROOT / "warehouse" / "chdb"
MODELS = ROOT / "models"
SEMANTIC = ROOT / "semantic"
REPORTS = ROOT / "reports"
DOCS = ROOT / "docs"

SEED = 360
# The synthetic data window. The "as of" time is when the last load finished.
WINDOW_START = "2025-10-01"
WINDOW_END = "2026-09-30"
AS_OF = "2026-10-01 06:00:00"


def _t(tenant_id, name, trade, city, state, zip3, area_codes, utc_offset, persons, provider_id, **knobs):
    """One made up contractor. The knobs give each one its own habits, so peer benchmarks differ."""
    return {"tenant_id": tenant_id, "name": f"{name} (synthetic)", "trade": trade, "city": city, "state": state,
            "zip3": zip3, "area_codes": area_codes, "utc_offset": utc_offset, "persons": persons,
            "provider_id": provider_id, **knobs}


# phone_style: how this tenant's carrier logs caller numbers. miss_rate: inbound calls nobody picks up.
# after_hours_ai: the AI agent calls leads back at night too. renewal: membership renewal chance.
# booking_skill: multiplies the chance a connected lead books.
TENANTS = [
    _t("tnt_alpine", "Alpine Comfort HVAC", "HVAC", "Denver", "CO", "802", ["303", "720"], -6, 8500,
       "6f1c2a8e-1b7d-4c55-9a51-0a1e3c7d2b01", phone_style="e164", miss_rate=0.04, after_hours_ai=True,
       renewal=0.72, booking_skill=1.00),
    _t("tnt_bayside", "Bayside Plumbing & Drain", "Plumbing", "Oakland", "CA", "946", ["510", "341"], -7, 6000,
       "0b9d4e27-5c3a-4f0e-8d6b-7e2f19a4c302", phone_style="plain10", miss_rate=0.09, after_hours_ai=False,
       renewal=0.72, booking_skill=0.95),
    _t("tnt_lonestar", "Lone Star Electric", "Electrical", "Austin", "TX", "787", ["512", "737"], -5, 4200,
       "c4a7e912-3d6b-48f1-b2e0-5f8a61d9e403", phone_style="plain11", miss_rate=0.06, after_hours_ai=False,
       renewal=0.58, booking_skill=0.90),
    _t("tnt_summit", "Summit Roofing", "Roofing", "Seattle", "WA", "981", ["206", "425"], -7, 3600,
       "9e2b7c14-6a3f-4d81-b5c2-1f7e8a9d0c04", phone_style="dash", miss_rate=0.11, after_hours_ai=False,
       renewal=0.50, booking_skill=0.80),
    _t("tnt_desert", "Desert Air HVAC", "HVAC", "Phoenix", "AZ", "850", ["602", "480"], -7, 7800,
       "2d5f8a31-7c4e-4b92-a6d3-8e1f0b2c7d05", phone_style="e164", miss_rate=0.05, after_hours_ai=True,
       renewal=0.78, booking_skill=1.08),
    _t("tnt_peachtree", "Peachtree Plumbing", "Plumbing", "Atlanta", "GA", "303", ["404", "678"], -4, 5400,
       "7a1c3e58-2b9d-4f60-8c74-5d2e9f1a3b06", phone_style="paren", miss_rate=0.07, after_hours_ai=False,
       renewal=0.66, booking_skill=1.00),
    _t("tnt_lakeshore", "Lakeshore Electric", "Electrical", "Chicago", "IL", "606", ["312", "773"], -5, 4800,
       "4b8e2f97-1d6c-4a35-9e08-6c3a7b5d1e07", phone_style="plain11", miss_rate=0.05, after_hours_ai=True,
       renewal=0.63, booking_skill=1.05),
    _t("tnt_harbor", "Harbor Heating & Cooling", "HVAC", "Boston", "MA", "021", ["617", "857"], -4, 4200,
       "8c3d6a20-5e1b-4c7f-a2d9-3b6e0f8c4a08", phone_style="dash", miss_rate=0.08, after_hours_ai=False,
       renewal=0.70, booking_skill=0.92),
    _t("tnt_gulf", "Gulf Coast Roofing", "Roofing", "Houston", "TX", "770", ["713", "832"], -5, 3000,
       "5f9a1b46-8d2c-4e73-b1f5-7a4c2e9d6b09", phone_style="plain10", miss_rate=0.13, after_hours_ai=False,
       renewal=0.48, booking_skill=0.85),
    _t("tnt_twincities", "Twin Cities Plumbing", "Plumbing", "Minneapolis", "MN", "554", ["612", "651"], -5, 2400,
       "1e6c4d83-9a7b-4f2e-8d51-2c9b6a3f7e10", phone_style="dot", miss_rate=0.06, after_hours_ai=True,
       renewal=0.68, booking_skill=1.02),
]
