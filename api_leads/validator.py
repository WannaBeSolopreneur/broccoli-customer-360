"""Offline validator for API Leads payloads, written from the public docs.

It never calls the network. Use it in a partner's CI to catch a 400 before
sending. Errors match the documented rules. Warnings flag documented gotchas
that do not fail the request (for example reserved additionalContext keys).
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker

SPEC = Path(__file__).with_name("openapi.yaml")
UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
RESERVED_CONTEXT_KEYS = {"comments": "description", "job_type": "serviceType", "source": "source",
                         "customer_email": "customer.email", "greeting_phrase": "greetingPhrase"}


@dataclass
class Result:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _schema() -> dict:
    spec = yaml.safe_load(SPEC.read_text())
    comps = spec["components"]["schemas"]
    # Resolve local refs so jsonschema can use the request schema on its own.
    def resolve(node):
        if isinstance(node, dict):
            if "$ref" in node:
                return resolve(comps[node["$ref"].split("/")[-1]])
            return {k: resolve(v) for k, v in node.items()}
        if isinstance(node, list):
            return [resolve(x) for x in node]
        return node
    return resolve(comps["LeadRequest"])


_VALIDATOR = Draft202012Validator(_schema(), format_checker=FormatChecker())


def to_e164(phone: str) -> str | None:
    """Return E.164 for an accepted phone string, else None."""
    if re.fullmatch(r"\+[1-9]\d{1,14}", phone):
        return phone
    if re.fullmatch(r"\d{10}", phone):
        return "+1" + phone
    if re.fullmatch(r"1\d{10}", phone):
        return "+" + phone
    return None


def validate(payload: dict) -> Result:
    res = Result()
    for err in sorted(_VALIDATOR.iter_errors(payload), key=lambda e: list(e.path)):
        where = ".".join(str(p) for p in err.path) or "(root)"
        res.errors.append(f"{where}: {err.message}")
    # Rules the schema cannot say on its own.
    pid = payload.get("providerId")
    if isinstance(pid, str) and not UUID_RE.match(pid):
        res.errors.append("providerId: must be a UUID")
    cust = payload.get("customer")
    if isinstance(cust, dict):
        email = cust.get("email")
        if isinstance(email, str) and not EMAIL_RE.match(email):
            res.errors.append("customer.email: must be a valid email address")
        if not cust.get("name") and not (cust.get("firstName") and cust.get("lastName")):
            res.warnings.append("customer: no name, or firstName and lastName. The docs do not require it, "
                                "but the {first_name} greeting token needs a first name.")
    ctx = payload.get("additionalContext")
    if isinstance(ctx, dict):
        for k in ctx:
            if k in RESERVED_CONTEXT_KEYS:
                res.warnings.append(f"additionalContext.{k}: overwritten by {RESERVED_CONTEXT_KEYS[k]}. Use that field instead.")
    if "externalLeadId" not in payload:
        res.warnings.append("externalLeadId: not sent. Every request will create a new lead, so retries make duplicates.")
    return res


def main():
    files = sys.argv[1:]
    if not files:
        print("usage: python -m api_leads.validator payload.json [more.json]")
        sys.exit(2)
    bad = 0
    for f in files:
        r = validate(json.loads(Path(f).read_text()))
        print(f"{f}: {'OK' if r.ok else 'FAIL'}")
        for e in r.errors:
            print(f"  error: {e}")
        for w in r.warnings:
            print(f"  warning: {w}")
        bad += not r.ok
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
