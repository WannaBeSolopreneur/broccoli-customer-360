"""The cleaning functions every source goes through."""
import pytest


@pytest.mark.parametrize("raw,expected", [
    ("(303) 555-0142", "+13035550142"),
    ("303-555-0142", "+13035550142"),
    ("1-303-555-0142", "+13035550142"),
    ("+1 303 555 0142", "+13035550142"),
    ("303.555.0142", "+13035550142"),
    ("3035550142", "+13035550142"),
    ("555", None),
    ("", None),
])
def test_phone_to_e164(wh, raw, expected):
    assert wh.scalar(f"SELECT c360_e164('{raw}') AS v") == expected


@pytest.mark.parametrize("raw,expected", [
    ("  Jane.Doe@Example.COM ", "jane.doe@example.com"),
    ("", None),
    ("not-an-email", None),
])
def test_email(wh, raw, expected):
    assert wh.scalar(f"SELECT c360_email('{raw}') AS v") == expected


def test_street_variants_match(wh):
    a = wh.scalar("SELECT c360_street_key('123 North Main Street Apt 4') AS v")
    b = wh.scalar("SELECT c360_street_key('123 N Main St') AS v")
    assert a == b


@pytest.mark.parametrize("raw,expected", [("80203-1234", "80203"), ("80203", "80203"), ("", None)])
def test_zip5(wh, raw, expected):
    assert wh.scalar(f"SELECT c360_zip5('{raw}') AS v") == expected
