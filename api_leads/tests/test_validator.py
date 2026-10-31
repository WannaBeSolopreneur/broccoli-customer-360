"""Offline tests. Every rule comes from docs.broccoli.com/api-leads/specification."""
import copy
import json
from pathlib import Path

import pytest
import yaml

from api_leads.validator import SPEC, to_e164, validate

ROOT = Path(__file__).resolve().parents[2]
GOOD = json.loads((ROOT / "api_leads" / "examples" / "docs_example.json").read_text())


def bad(**changes):
    p = copy.deepcopy(GOOD)
    for path, val in changes.items():
        node = p
        keys = path.split("__")
        for k in keys[:-1]:
            node = node[k]
        if val is ...:
            node.pop(keys[-1])
        else:
            node[keys[-1]] = val
    return validate(p)


def test_spec_is_openapi_31():
    spec = yaml.safe_load(SPEC.read_text())
    assert spec["openapi"].startswith("3.1")
    assert "/leads/inbound/webhook" in spec["paths"]
    assert "docs.broccoli.com/api-leads/specification" in SPEC.read_text()


def test_docs_example_is_valid():
    r = validate(GOOD)
    assert r.ok, r.errors
    assert r.warnings == []


@pytest.mark.parametrize("phone", ["+18015551234", "8015551234", "18015551234", "+447700900123"])
def test_accepted_phones(phone):
    assert bad(customer__phone=phone).ok


@pytest.mark.parametrize("phone", ["801-555-1234", "(801) 555-1234", "28015551234", "555", "+0123"])
def test_rejected_phones(phone):
    assert not bad(customer__phone=phone).ok


def test_to_e164():
    assert to_e164("8015551234") == "+18015551234"
    assert to_e164("18015551234") == "+18015551234"
    assert to_e164("801-555-1234") is None


@pytest.mark.parametrize("change", [
    {"providerId": ...},
    {"customer": ...},
    {"customer__phone": ...},
    {"providerId": "not-a-uuid"},
    {"customer__email": "jane.example.com"},
    {"preferredChannel": "EMAIL"},
    {"greetingPhrase": "x" * 301},
    {"additionalContext": {"rooms": 3}},
    {"additionalContext": {"nested": {"a": "b"}}},
    {"address": {"street": "1 Main St", "city": "Provo", "state": "UT"}},
    {"address": 42},
])
def test_invalid_payloads(change):
    assert not bad(**change).ok


def test_unknown_field_rejected_at_every_level():
    assert not bad(priority="high").ok
    assert not bad(customer__middleName="Q").ok
    assert not bad(address__zip="84601").ok


def test_address_as_string_and_country_optional():
    assert bad(address="123 Main St, Provo, UT 84601").ok
    assert bad(address__country="US").ok


def test_greeting_limit_is_inclusive():
    assert bad(greetingPhrase="Hi {first_name}" + "x" * (300 - len("Hi {first_name}"))).ok


def test_reserved_context_key_is_a_warning_not_an_error():
    r = bad(additionalContext={"job_type": "AC repair"})
    assert r.ok
    assert any("serviceType" in w for w in r.warnings)


def test_missing_external_id_warns_about_duplicates():
    r = bad(externalLeadId=...)
    assert r.ok and any("duplicates" in w for w in r.warnings)


def test_every_synthetic_lead_passes():
    """The leads in this repo's synthetic data follow the documented contract."""
    files = sorted((ROOT / "data" / "raw" / "leads").glob("*.jsonl"))
    if not files:
        pytest.skip("run make generate first")
    n = 0
    for f in files:
        for line in f.read_text().splitlines():
            r = validate(json.loads(line)["payload"])
            assert r.ok, (f.name, r.errors)
            n += 1
    assert n > 1000
