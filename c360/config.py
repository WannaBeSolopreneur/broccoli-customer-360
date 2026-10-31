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
WINDOW_START = "2026-04-01"
WINDOW_END = "2026-09-30"
AS_OF = "2026-10-01 06:00:00"

TENANTS = [
    # tenant_id, display name, trade, city, state, zip prefix, area codes, utc offset in hours, persons
    {"tenant_id": "tnt_alpine", "name": "Alpine Comfort HVAC (synthetic)", "trade": "HVAC",
     "city": "Denver", "state": "CO", "zip3": "802", "area_codes": ["303", "720"], "utc_offset": -6,
     "persons": 2800, "provider_id": "6f1c2a8e-1b7d-4c55-9a51-0a1e3c7d2b01"},
    {"tenant_id": "tnt_bayside", "name": "Bayside Plumbing & Drain (synthetic)", "trade": "Plumbing",
     "city": "Oakland", "state": "CA", "zip3": "946", "area_codes": ["510", "341"], "utc_offset": -7,
     "persons": 2000, "provider_id": "0b9d4e27-5c3a-4f0e-8d6b-7e2f19a4c302"},
    {"tenant_id": "tnt_lonestar", "name": "Lone Star Electric (synthetic)", "trade": "Electrical",
     "city": "Austin", "state": "TX", "zip3": "787", "area_codes": ["512", "737"], "utc_offset": -5,
     "persons": 1400, "provider_id": "c4a7e912-3d6b-48f1-b2e0-5f8a61d9e403"},
]
