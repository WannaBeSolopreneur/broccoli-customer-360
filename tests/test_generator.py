"""The synthetic data is deterministic and clearly fake."""
import hashlib
import json
from pathlib import Path

from c360 import config, generate


def _digest(root: Path) -> str:
    h = hashlib.md5()
    for p in sorted(root.rglob("*")):
        if p.is_file():
            h.update(p.relative_to(root).as_posix().encode())
            h.update(p.read_bytes())
    return h.hexdigest()


def test_same_seed_same_files(tmp_path):
    generate.Gen().run(tmp_path / "a")
    generate.Gen().run(tmp_path / "b")
    assert _digest(tmp_path / "a") == _digest(tmp_path / "b")


def test_phones_and_emails_are_fake(tmp_path):
    generate.Gen().run(tmp_path)
    for line in (tmp_path / "raw" / "leads" / "tnt_alpine.jsonl").read_text().splitlines()[:300]:
        cust = json.loads(line)["payload"]["customer"]
        digits = "".join(c for c in cust["phone"] if c.isdigit())[-10:]
        assert digits[3:6] == "555"
        if cust.get("email"):
            domain = cust["email"].strip().lower().split("@")[1]
            # example.com, .net and .org are reserved for docs and tests (RFC 2606).
            assert domain.rsplit(".", 2)[-2:] in (["example", "com"], ["example", "net"], ["example", "org"])


def test_marked_synthetic():
    tenants = json.loads((config.RAW / "tenants.json").read_text())
    assert all("(synthetic)" in t["name"] for t in tenants)
