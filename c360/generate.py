"""Generate synthetic, messy, multi-source data for three made-up contractors.

Everything here is fake. Names, phones (555 exchange), emails (example.* domains)
and addresses are random. The data is seeded, so every run gives the same files.

Outputs (data/raw/<source>/<tenant_id>.<ext>):
  calls      AI agent call and text log (inbound calls plus lead follow-up)
  leads      API Leads webhook archive, payloads shaped like docs.broccoli.com
  jobs       ServiceTitan style job export
  invoices   billing system export (service and membership invoices)
  tickets    support desk export
Ground truth person ids go to data/ground_truth/ only. They are used for
scoring entity resolution and never read by the warehouse models.
"""
from __future__ import annotations

import csv
import json
import math
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from . import config

FIRST = ["James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael", "Linda", "William",
         "Elizabeth", "David", "Barbara", "Richard", "Susan", "Joseph", "Jessica", "Thomas", "Sarah",
         "Christopher", "Karen", "Daniel", "Nancy", "Matthew", "Lisa", "Anthony", "Margaret", "Steven",
         "Sandra", "Andrew", "Ashley", "Joshua", "Emily", "Kenneth", "Donna", "Kevin", "Michelle",
         "Brian", "Carol", "Edward", "Amanda", "Ronald", "Melissa", "Timothy", "Deborah", "Jason",
         "Stephanie", "Jeffrey", "Rebecca", "Ryan", "Laura", "Jacob", "Sharon", "Gary", "Cynthia",
         "Nicholas", "Kathleen", "Eric", "Amy", "Jonathan", "Angela", "Samuel", "Rosa", "Luis",
         "Priya", "Wei", "Aisha", "Omar", "Mei", "Diego", "Fatima", "Hiroshi", "Ana", "Carlos", "Nguyen"]
LAST = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez",
        "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore",
        "Jackson", "Martin", "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark",
        "Ramirez", "Lewis", "Robinson", "Walker", "Young", "Allen", "King", "Wright", "Scott", "Torres",
        "Nguyen", "Hill", "Flores", "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell",
        "Mitchell", "Carter", "Roberts", "Patel", "Khan", "Chen", "Kim", "Okafor", "Schmidt", "Rossi",
        "Kowalski", "Haddad", "Novak", "Silva", "Murphy", "OBrien", "Sullivan", "Bennett", "Foster"]
NICK = {"Robert": "Bob", "William": "Bill", "Richard": "Rick", "Joseph": "Joe", "Thomas": "Tom",
        "Christopher": "Chris", "Daniel": "Dan", "Matthew": "Matt", "Anthony": "Tony", "Steven": "Steve",
        "Andrew": "Andy", "Joshua": "Josh", "Kenneth": "Ken", "Edward": "Ed", "Ronald": "Ron",
        "Timothy": "Tim", "Jeffrey": "Jeff", "Nicholas": "Nick", "Jonathan": "Jon", "Samuel": "Sam",
        "Elizabeth": "Liz", "Patricia": "Pat", "Jennifer": "Jen", "Margaret": "Peggy", "Susan": "Sue",
        "Jessica": "Jess", "Rebecca": "Becky", "Katherine": "Kate", "Kathleen": "Kathy", "Michael": "Mike",
        "James": "Jim", "Deborah": "Debbie", "Cynthia": "Cindy", "Stephanie": "Steph", "Amanda": "Mandy"}
STREETS = ["Maple", "Oak", "Pine", "Cedar", "Elm", "Washington", "Lake", "Hill", "Park", "Sunset",
           "Ridge", "Meadow", "Willow", "Highland", "Lincoln", "Jefferson", "Spring", "Valley",
           "Forest", "River", "Aspen", "Juniper", "Canyon", "Mesa", "Harbor", "Bluebonnet", "Pecan",
           "Live Oak", "Magnolia", "Cypress", "Sycamore", "Chestnut", "Madison", "Franklin", "Grant"]
STYPES = [("Street", ["St", "St.", "Street", "STREET"]), ("Avenue", ["Ave", "Ave.", "Avenue", "Av"]),
          ("Drive", ["Dr", "Dr.", "Drive"]), ("Road", ["Rd", "Rd.", "Road"]),
          ("Lane", ["Ln", "Lane"]), ("Court", ["Ct", "Court"]), ("Boulevard", ["Blvd", "Boulevard"]),
          ("Way", ["Way"]), ("Place", ["Pl", "Place"])]
DIRS = [("North", ["N", "N.", "North"]), ("South", ["S", "S.", "South"]),
        ("East", ["E", "E.", "East"]), ("West", ["W", "W.", "West"])]
EMAIL_DOMAINS = ["example.com", "example.net", "example.org", "mail.example.com", "inbox.example.net"]
WORK_DOMAINS = ["corp.example.com", "work.example.org", "company.example.net"]

TRADE_SERVICES = {
    "HVAC": [("AC repair", 420, 0.6), ("Furnace repair", 380, 0.6), ("AC tune-up", 129, 0.2),
             ("Furnace tune-up", 119, 0.2), ("New AC install", 7800, 0.35), ("Heat pump install", 11200, 0.3),
             ("Duct cleaning", 450, 0.3), ("Thermostat install", 310, 0.3)],
    "Plumbing": [("Drain cleaning", 260, 0.4), ("Water heater repair", 480, 0.5),
                 ("Water heater install", 2600, 0.3), ("Leak repair", 390, 0.6), ("Sewer line camera", 299, 0.2),
                 ("Toilet repair", 240, 0.4), ("Repipe estimate", 0, 0.0), ("Garbage disposal install", 520, 0.3)],
    "Electrical": [("Panel upgrade", 3400, 0.35), ("EV charger install", 1650, 0.3), ("Outlet repair", 210, 0.4),
                   ("Lighting install", 640, 0.5), ("Whole home surge protector", 480, 0.2),
                   ("Generator install", 9200, 0.3), ("Breaker troubleshooting", 280, 0.5)],
}
LEAD_SOURCES = ["web-form", "google-lsa", "angi", "yelp", "meta-ads", "thumbtack"]
MEMBERSHIP_PRICE = {"HVAC": 189.0, "Plumbing": 149.0, "Electrical": 129.0}


def _ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


class Gen:
    def __init__(self, seed: int = config.SEED):
        self.r = random.Random(seed)
        self.start = datetime.fromisoformat(config.WINDOW_START)
        self.end = datetime.fromisoformat(config.WINDOW_END) + timedelta(days=1)
        self.as_of = datetime.fromisoformat(config.AS_OF)
        self.used_phones: set[str] = set()
        self.truth: list[dict] = []
        self.rows: dict[str, dict[str, list]] = {}

    # ---------- identity helpers ----------
    def uid(self, prefix: str) -> str:
        return f"{prefix}_{uuid.UUID(int=self.r.getrandbits(128)).hex[:12]}"

    def phone(self, area_codes: list[str]) -> str:
        while True:
            p = f"{self.r.choice(area_codes)}555{self.r.randint(0, 9999):04d}"
            if p not in self.used_phones and not p.endswith("5550100"):
                self.used_phones.add(p)
                return p

    def fmt_phone(self, digits10: str, style: str | None = None) -> str:
        a, b, c = digits10[:3], digits10[3:6], digits10[6:]
        styles = {
            "e164": f"+1{digits10}", "dash": f"{a}-{b}-{c}", "paren": f"({a}) {b}-{c}",
            "plain10": digits10, "plain11": f"1{digits10}", "dash11": f"1-{a}-{b}-{c}",
            "dot": f"{a}.{b}.{c}", "space": f"+1 {a} {b} {c}",
        }
        style = style or self.r.choice(list(styles))
        return styles[style]

    def messy_email(self, email: str | None) -> str:
        if not email:
            return ""
        roll = self.r.random()
        if roll < 0.25:
            return email.upper()
        if roll < 0.45:
            return email.capitalize()
        if roll < 0.55:
            return f"  {email} "
        return email

    def typo(self, s: str) -> str:
        if len(s) < 4:
            return s
        i = self.r.randint(1, len(s) - 2)
        kind = self.r.random()
        if kind < 0.4:
            return s[:i] + s[i + 1:]                       # drop a letter
        if kind < 0.8:
            return s[:i] + s[i + 1] + s[i] + s[i + 2:]     # swap two letters
        return s[:i] + s[i] + s[i:]                        # double a letter

    def name_variant(self, first: str, last: str, p_typo: float = 0.05, p_nick: float = 0.06) -> tuple[str, str]:
        f, l = first, last
        roll = self.r.random()
        if roll < p_nick and first in NICK:
            f = NICK[first]
        elif roll < p_nick + p_typo:
            if self.r.random() < 0.5:
                f = self.typo(f)
            else:
                l = self.typo(l)
        case = self.r.random()
        if case < 0.08:
            f, l = f.upper(), l.upper()
        elif case < 0.14:
            f, l = f.lower(), l.lower()
        return f, l

    def addr_variant(self, a: dict) -> dict:
        stype_full = a["stype"]
        stype_opts = dict(STYPES)[stype_full]
        street = a["street"]
        if self.r.random() < 0.04:
            street = self.typo(street)
        parts = [str(a["num"])]
        if a["dir"]:
            parts.append(self.r.choice(dict(DIRS)[a["dir"]]))
        parts += [street, self.r.choice(stype_opts)]
        line = " ".join(parts)
        if a["unit"]:
            line += self.r.choice([f" Apt {a['unit']}", f" #{a['unit']}", f" Unit {a['unit']}", f", Apt {a['unit']}"])
        if self.r.random() < 0.07:
            line = line.upper()
        z = a["zip"]
        zroll = self.r.random()
        if zroll < 0.08:
            z = ""
        elif zroll < 0.16:
            z = f"{z}-{self.r.randint(1000, 9999)}"
        return {"street": line, "city": a["city"] if self.r.random() > 0.05 else a["city"].upper(),
                "state": a["state"], "postalCode": z}

    def addr_string(self, v: dict) -> str:
        bits = [v["street"], v["city"], f"{v['state']} {v['postalCode']}".strip()]
        return ", ".join(b for b in bits if b)

    def in_window(self) -> datetime:
        span = (self.end - self.start).total_seconds()
        return self.start + timedelta(seconds=self.r.random() * span)

    def emit(self, source: str, tenant: str, row: dict, person_id: str | None, record_id: str):
        self.rows.setdefault(source, {}).setdefault(tenant, []).append(row)
        if person_id is not None:
            self.truth.append({"tenant_id": tenant, "source": source, "record_id": record_id,
                               "person_id": person_id})

    # ---------- people ----------
    def make_people(self, t: dict, donors: list[dict]) -> list[dict]:
        people: list[dict] = []
        used_emails: set[str] = set()
        n = t["persons"]
        while len(people) < n:
            pid = self.uid("p")
            if people and self.r.random() < 0.10:
                # A second adult in an existing household. Same address and last name.
                host = self.r.choice(people)
                first = self.r.choice([x for x in FIRST if x != host["first"]])
                p = {"person_id": pid, "first": first, "last": host["last"], "cell": self.phone(t["area_codes"]),
                     "address": host["address"], "household": host["household"], "landline": host["landline"]}
            elif donors and self.r.random() < 0.04:
                # Same human is also a customer of another tenant. Keys must stay separate per tenant.
                d = self.r.choice(donors)
                p = {"person_id": pid, "first": d["first"], "last": d["last"], "cell": d["cell"],
                     "address": self.new_address(t), "household": self.uid("h"), "landline": None,
                     "email": d.get("email")}
            else:
                p = {"person_id": pid, "first": self.r.choice(FIRST), "last": self.r.choice(LAST),
                     "cell": self.phone(t["area_codes"]), "address": self.new_address(t),
                     "household": self.uid("h"),
                     "landline": self.phone(t["area_codes"]) if self.r.random() < 0.15 else None}
            if "email" not in p:
                if self.r.random() < 0.85:
                    sep = self.r.choice([".", "_", ""])
                    num = str(self.r.randint(1, 99)) if self.r.random() < 0.4 else ""
                    email = f"{p['first'].lower()}{sep}{p['last'].lower()}{num}@{self.r.choice(EMAIL_DOMAINS)}"
                    while email in used_emails:   # two real people do not share one personal inbox
                        email = email.replace("@", f"{self.r.randint(1, 9)}@")
                    p["email"] = email
                else:
                    p["email"] = None
            if p.get("email"):
                used_emails.add(p["email"])
            p["work_email"] = (f"{p['first'][0].lower()}{p['last'].lower()}@{self.r.choice(WORK_DOMAINS)}"
                               if self.r.random() < 0.12 else None)
            people.append(p)
        return people

    def new_address(self, t: dict) -> dict:
        return {"num": self.r.randint(100, 19999), "street": self.r.choice(STREETS),
                "stype": self.r.choice(STYPES)[0],
                "dir": self.r.choice(DIRS)[0] if self.r.random() < 0.2 else None,
                "unit": str(self.r.randint(1, 40)) if self.r.random() < 0.1 else None,
                "city": t["city"], "state": t["state"], "zip": f"{t['zip3']}{self.r.randint(1, 60):02d}"}

    # ---------- per tenant event simulation ----------
    def local_hour(self, t: dict, utc: datetime) -> int:
        return (utc + timedelta(hours=t["utc_offset"])).hour

    def next_open(self, t: dict, utc: datetime) -> datetime:
        """Next 8am local time at or after utc, as UTC."""
        local = utc + timedelta(hours=t["utc_offset"])
        if local.hour >= 20:
            local = (local + timedelta(days=1)).replace(hour=8, minute=0, second=0)
        elif local.hour < 8:
            local = local.replace(hour=8, minute=0, second=0)
        return local - timedelta(hours=t["utc_offset"])

    def caller_fmt(self, t: dict, digits: str) -> str:
        # Each tenant's phone carrier logs numbers a little differently.
        style = {"tnt_alpine": "e164", "tnt_bayside": "plain10", "tnt_lonestar": "plain11"}[t["tenant_id"]]
        if self.r.random() < 0.1:
            style = "e164"
        return self.fmt_phone(digits, style)

    def run_tenant(self, t: dict, people: list[dict]):
        tid = t["tenant_id"]
        services = TRADE_SERVICES[t["trade"]]
        st_ids: dict[str, list[str]] = {}
        used_job_numbers: set[str] = set()
        after_hours_first_contact = tid == "tnt_alpine"

        def st_customer(p: dict) -> str:
            ids = st_ids.setdefault(p["person_id"], [])
            if not ids or (len(ids) == 1 and self.r.random() < 0.05):
                ids.append(f"{self.r.randint(10_000_000, 99_999_999)}")
            return ids[-1] if self.r.random() < 0.7 else ids[0]

        def add_job(p: dict, created: datetime, source: str, ref: str | None):
            if created > self.as_of:
                return None
            svc, base, sd = self.r.choice(services)
            sched = created + timedelta(days=self.r.uniform(0.3, 9))
            if sched > self.as_of:
                status, completed, revenue = "Scheduled", "", 0.0
            elif self.r.random() < 0.12:
                status, completed, revenue = "Canceled", "", 0.0
            else:
                status = "Completed"
                completed = _ts(min(sched + timedelta(hours=self.r.uniform(1, 5)), self.as_of - timedelta(minutes=60)))
                revenue = round(base * math.exp(self.r.gauss(0, sd)), 2) if base else 0.0
            f, l = self.name_variant(p["first"], p["last"], p_typo=0.03, p_nick=0.03)
            v = self.addr_variant(p["address"])
            ph = p["landline"] if (p["landline"] and self.r.random() < 0.4) else p["cell"]
            email = p["email"] if self.r.random() < 0.8 else ""
            job_id = self.uid("job")
            job_number = str(self.r.randint(100000, 999999))
            while job_number in used_job_numbers:
                job_number = str(self.r.randint(100000, 999999))
            used_job_numbers.add(job_number)
            row = {"job_id": job_id, "job_number": job_number, "st_customer_id": st_customer(p),
                   "customer_name": f"{l}, {f}" if self.r.random() < 0.5 else f"{f} {l}",
                   "customer_phone": self.fmt_phone(ph, "paren" if self.r.random() < 0.7 else None),
                   "customer_email": self.messy_email(email),
                   "location_street": v["street"], "location_city": v["city"], "location_state": v["state"],
                   "location_zip": v["postalCode"], "business_unit": t["trade"], "job_type": svc,
                   "booking_source": source, "broccoli_ref": ref or "", "created_on": _ts(created),
                   "scheduled_start": _ts(sched), "status": status, "completed_on": completed,
                   "total_revenue": f"{revenue:.2f}", "_loaded_at": _ts(self.as_of - timedelta(minutes=self.r.randint(5, 50)))}
            self.emit("jobs", tid, row, p["person_id"], job_id)
            if status == "Completed" and revenue > 0:
                add_invoice(p, row, revenue, sched)
                if self.r.random() < 0.06:
                    add_membership(p, sched, renewal=False)
            return row

        def bill_identity(p: dict) -> dict:
            f, l = self.name_variant(p["first"], p["last"])
            style = self.r.random()
            if style < 0.3:
                name = f"{l.upper()}, {f.upper()}"
            elif style < 0.45:
                name = f"{f[0]}. {l}"
            else:
                name = f"{f} {l}"
            email = p["email"]
            if p["work_email"] and self.r.random() < 0.5:
                email = p["work_email"]
            if self.r.random() < 0.15:
                email = None
            ph = p["landline"] if (p["landline"] and self.r.random() < 0.5) else p["cell"]
            v = self.addr_variant(p["address"])
            return {"bill_to_name": name, "bill_to_email": self.messy_email(email),
                    "bill_to_phone": self.fmt_phone(ph, "dot" if self.r.random() < 0.6 else None)
                    if self.r.random() > 0.08 else "",
                    "bill_to_address": self.addr_string(v)}

        def add_invoice(p: dict, job: dict, amount: float, when: datetime):
            inv_id = self.uid("inv")
            inv_date = min(when + timedelta(days=self.r.uniform(0, 2)), self.as_of - timedelta(minutes=30))
            paid_roll = self.r.random()
            paid = amount if paid_roll < 0.86 else (0.0 if paid_roll < 0.97 else round(amount * 0.5, 2))
            status = "paid" if paid == amount else ("open" if paid == 0 else "partial")
            row = {"invoice_id": inv_id, "invoice_number": f"INV-{self.r.randint(100000, 999999)}",
                   "invoice_type": "service", "job_number": job["job_number"] if self.r.random() < 0.93 else "",
                   **bill_identity(p), "membership_id": "", "membership_period_start": "",
                   "membership_period_end": "", "invoice_date": _ts(inv_date),
                   "due_date": _ts(inv_date + timedelta(days=30)), "amount": f"{amount:.2f}",
                   "amount_paid": f"{paid:.2f}", "status": status,
                   "_loaded_at": _ts(self.as_of - timedelta(minutes=self.r.randint(30, 300)))}
            self.emit("invoices", tid, row, p["person_id"], inv_id)

        def add_membership(p: dict, start: datetime, renewal: bool):
            inv_id = self.uid("inv")
            end = start + timedelta(days=365)
            price = MEMBERSHIP_PRICE[t["trade"]]
            row = {"invoice_id": inv_id, "invoice_number": f"INV-{self.r.randint(100000, 999999)}",
                   "invoice_type": "membership", "job_number": "", **bill_identity(p),
                   "membership_id": self.uid("mem"),
                   "membership_period_start": start.strftime("%Y-%m-%d"),
                   "membership_period_end": end.strftime("%Y-%m-%d"),
                   "invoice_date": _ts(start), "due_date": _ts(start + timedelta(days=15)),
                   "amount": f"{price:.2f}", "amount_paid": f"{price:.2f}", "status": "paid",
                   "_loaded_at": _ts(self.as_of - timedelta(minutes=self.r.randint(30, 300)))}
            self.emit("invoices", tid, row, p["person_id"], inv_id)
            return end

        def call_row(p: dict | None, when: datetime, direction: str, channel: str, phone_digits: str,
                     answered: str, outcome: str, intent: str, booked: bool, lead_ref: str = "",
                     duration: int = 0, caller_name: str = ""):
            cid = self.uid("call")
            phone = (self.caller_fmt(t, phone_digits) if direction == "inbound" else f"+1{phone_digits}")
            row = {"call_id": cid, "started_at": _ts(when), "direction": direction, "channel": channel,
                   "customer_phone": phone, "answered_by": answered, "outcome": outcome, "intent": intent,
                   "booked": "true" if booked else "false", "duration_sec": str(duration),
                   "lead_external_id": lead_ref, "caller_name": caller_name,
                   "_loaded_at": _ts(self.as_of - timedelta(minutes=self.r.randint(1, 20)))}
            # Only inbound non spam calls carry an identity we try to resolve.
            self.emit("calls", tid, row, p["person_id"] if (p and direction == "inbound") else None, cid)
            return row

        # Memberships that started last year. Their renewals fall inside the window.
        for p in people:
            if self.r.random() < 0.22:
                start = self.start - timedelta(days=self.r.uniform(0, 364))
                end = add_membership(p, start, renewal=False)
                renew_on = end + timedelta(days=self.r.uniform(-20, 20))
                if end <= self.as_of and renew_on <= self.as_of:
                    if self.r.random() < (0.72 if tid != "tnt_lonestar" else 0.58):
                        add_membership(p, renew_on, renewal=True)
                        if self.r.random() < 0.3:
                            when = max(end - timedelta(days=self.r.uniform(1, 25)), self.start)
                            call_row(p, when, "inbound", "voice", p["cell"], "ai_agent", "membership_renewed",
                                     "membership_renewal", False, duration=self.r.randint(60, 300))

        for p in people:
            # Inbound calls to the AI agent.
            for _ in range(self.r.choices([0, 1, 2, 3], [0.35, 0.4, 0.17, 0.08])[0]):
                when = self.in_window()
                digits = p["landline"] if (p["landline"] and self.r.random() < 0.5) else p["cell"]
                roll = self.r.random()
                miss = {"tnt_alpine": 0.04, "tnt_bayside": 0.09, "tnt_lonestar": 0.06}[tid]
                if roll < miss:
                    call_row(p, when, "inbound", "voice", digits, "none", "missed", "unknown", False)
                    continue
                if roll < miss + 0.03:
                    call_row(p, when, "inbound", "voice", digits, "none", "abandoned", "unknown", False,
                             duration=self.r.randint(2, 15))
                    continue
                intent = self.r.choices(["repair", "install", "maintenance", "estimate", "billing_question"],
                                        [0.45, 0.15, 0.15, 0.15, 0.10])[0]
                book_p = {"repair": 0.62, "install": 0.4, "maintenance": 0.55, "estimate": 0.45,
                          "billing_question": 0.0}[intent]
                booked = self.r.random() < book_p
                outcome = "booked" if booked else self.r.choice(
                    ["quote_requested", "info_only", "transferred_to_staff", "callback_requested"])
                name = ""
                if self.r.random() < 0.5:
                    f, l = self.name_variant(p["first"], p["last"], p_typo=0.12)
                    name = f"{f} {l}"
                c = call_row(p, when, "inbound", "voice", digits, "ai_agent", outcome, intent, booked,
                             duration=self.r.randint(45, 600), caller_name=name)
                if booked:
                    add_job(p, when, "broccoli_ai_inbound", c["call_id"] if self.r.random() < 0.6 else None)

            # Leads sent through the API Leads webhook.
            n_leads = 0
            if self.r.random() < 0.42:
                n_leads = 2 if self.r.random() < 0.07 else 1
            for _ in range(n_leads):
                self.make_lead(t, p, add_job, call_row, after_hours_first_contact)

            # Work booked outside Broccoli (office staff or online booking).
            if self.r.random() < 0.25:
                add_job(p, self.in_window(), self.r.choice(["csr", "online_booking"]), None)

            # Support tickets.
            for _ in range(self.r.choices([0, 1, 2], [0.85, 0.12, 0.03])[0]):
                self.make_ticket(t, p)

        # Spam and robocalls. No real customer behind them.
        for _ in range(int(len(people) * 0.15)):
            digits = f"{self.r.choice(['800', '888', '214', '646', '415'])}555{self.r.randint(0, 9999):04d}"
            call_row(None, self.in_window(), "inbound", "voice", digits, "ai_agent", "spam", "spam", False,
                     duration=self.r.randint(5, 40))

    def make_lead(self, t, p, add_job, call_row, after_hours_first_contact):
        tid = t["tenant_id"]
        received = self.in_window()
        source = self.r.choice(LEAD_SOURCES)
        ext_id = f"{source}-{self.r.getrandbits(40):010x}"
        svc = self.r.choice(TRADE_SERVICES[t["trade"]])[0]
        f, l = self.name_variant(p["first"], p["last"])
        cust: dict = {"phone": self.fmt_phone(p["cell"], self.r.choice(["e164", "e164", "plain10", "plain11"]))}
        if self.r.random() < 0.5:
            cust["name"] = f"{f} {l}"
        else:
            cust["firstName"], cust["lastName"] = f, l
        if p["email"] and self.r.random() < 0.82:
            cust["email"] = self.messy_email(p["email"]).strip()
        payload: dict = {"providerId": t["provider_id"], "externalLeadId": ext_id, "customer": cust}
        if self.r.random() < 0.9:
            v = self.addr_variant(p["address"])
            if self.r.random() < 0.5 and v["postalCode"]:
                payload["address"] = {"street": v["street"], "city": v["city"], "state": v["state"],
                                      "postalCode": v["postalCode"]}
            else:
                payload["address"] = self.addr_string(v)
        payload["serviceType"] = svc
        if self.r.random() < 0.7:
            payload["description"] = self.r.choice(["Wants a quote", "Needs someone this week", "Urgent",
                                                    "Asked about financing", "Second opinion", "Noise from unit"])
        payload["source"] = source
        if self.r.random() < 0.6:
            payload["preferredChannel"] = self.r.choice(["CALL", "CHAT", "CALL_THEN_CHAT"])
        if self.r.random() < 0.3:
            payload["additionalContext"] = {"home_age": f"{self.r.randint(2, 70)} years"}
        sends = [received]
        if self.r.random() < 0.08:   # partner retried after a timeout, same externalLeadId
            sends.append(received + timedelta(seconds=self.r.randint(5, 120)))
        for i, s in enumerate(sends):
            row_id = self.uid("lrow")
            row = {"lead_row_id": row_id, "received_at": _ts(s), "test": False,
                   "_loaded_at": _ts(self.as_of - timedelta(minutes=self.r.randint(1, 30))), "payload": payload}
            self.emit("leads", tid, row, p["person_id"], row_id)

        # First contact and follow-up by the AI agent.
        channel_pref = payload.get("preferredChannel", "CALL_THEN_CHAT")
        local_h = self.local_hour(t, received)
        open_now = 8 <= local_h < 20
        if open_now or after_hours_first_contact:
            first = received + timedelta(seconds=self.r.choice([self.r.randint(4, 40)] * 8 + [self.r.randint(60, 900)] * 2))
        else:
            first = self.next_open(t, received) + timedelta(seconds=self.r.randint(5, 600))
        attempts = [first] + [self.next_open(t, first + timedelta(days=d, hours=self.r.uniform(0, 4))) +
                              timedelta(minutes=self.r.randint(0, 120)) for d in range(1, 5)]
        for i, when in enumerate(attempts):
            if when > self.as_of:   # the extract stops at the as of time
                break
            channel = "sms" if channel_pref == "CHAT" or (channel_pref == "CALL_THEN_CHAT" and i % 2 == 1) else "voice"
            connected = self.r.random() < (0.55 if i == 0 else 0.25)
            if not connected:
                call_row(p, when, "outbound", channel, p["cell"], "ai_agent", "no_answer" if channel == "voice" else "no_reply",
                         "lead_follow_up", False, lead_ref=ext_id, duration=self.r.randint(0, 30) if channel == "voice" else 0)
                continue
            booked = self.r.random() < 0.5
            c = call_row(p, when, "outbound", channel, p["cell"], "ai_agent", "booked" if booked else "not_interested",
                         "lead_follow_up", booked, lead_ref=ext_id,
                         duration=self.r.randint(60, 500) if channel == "voice" else 0)
            if booked:
                add_job(p, when, "broccoli_ai_lead", ext_id if self.r.random() < 0.6 else None)
            break

    def make_ticket(self, t, p):
        tid = t["tenant_id"]
        created = self.in_window()
        f, l = self.name_variant(p["first"], p["last"])
        email = p["email"] or (p["work_email"] if p["work_email"] else None)
        phone = self.fmt_phone(p["cell"]) if (not email or self.r.random() < 0.35) else ""
        category = self.r.choice(["billing", "scheduling", "complaint", "warranty", "membership"])
        hours = self.r.expovariate(1 / 20)
        resolved = created + timedelta(hours=hours)
        status = "solved" if resolved < self.as_of else "open"
        tk = self.uid("tkt")
        row = {"ticket_id": tk, "created_at": _ts(created),
               "channel": self.r.choice(["email", "sms", "web", "phone"]),
               "requester_name": f if self.r.random() < 0.3 else f"{f} {l}",
               "requester_email": self.messy_email(email), "requester_phone": phone,
               "category": category, "status": status,
               "resolved_at": _ts(resolved) if status == "solved" else "",
               "csat": str(self.r.choices([1, 2, 3, 4, 5], [0.05, 0.05, 0.1, 0.3, 0.5])[0]) if status == "solved" and self.r.random() < 0.4 else "",
               "_loaded_at": _ts(self.as_of - timedelta(minutes=self.r.randint(10, 90)))}
        self.emit("tickets", tid, row, p["person_id"], tk)

    # ---------- run ----------
    def run(self, out: Path = config.DATA):
        donors: list[dict] = []
        for t in config.TENANTS:
            people = self.make_people(t, donors)
            self.run_tenant(t, people)
            donors = donors + people[:200]
        raw = out / "raw"
        for source, by_tenant in self.rows.items():
            d = raw / source
            d.mkdir(parents=True, exist_ok=True)
            for tid, rows in by_tenant.items():
                rows.sort(key=lambda r: r.get("started_at") or r.get("received_at") or r.get("created_on")
                          or r.get("invoice_date") or r.get("created_at"))
                if source == "leads":
                    with open(d / f"{tid}.jsonl", "w") as fh:
                        for r in rows:
                            fh.write(json.dumps(r, sort_keys=True) + "\n")
                else:
                    with open(d / f"{tid}.csv", "w", newline="") as fh:
                        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
                        w.writeheader()
                        w.writerows(rows)
        gt = out / "ground_truth"
        gt.mkdir(parents=True, exist_ok=True)
        with open(gt / "identity_truth.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["tenant_id", "source", "record_id", "person_id"])
            w.writeheader()
            w.writerows(self.truth)
        tenants = [{k: t[k] for k in ("tenant_id", "name", "trade", "city", "state", "utc_offset", "provider_id")}
                   for t in config.TENANTS]
        (raw / "tenants.json").write_text(json.dumps(tenants, indent=2))
        (out / "README_SYNTHETIC.txt").write_text(
            "All files in this folder are synthetic. They were made by c360/generate.py with seed "
            f"{config.SEED}. No real people, phones, emails or addresses.\n")
        return {s: sum(len(v) for v in bt.values()) for s, bt in self.rows.items()}


def main():
    counts = Gen().run()
    for k, v in sorted(counts.items()):
        print(f"{k:10s} {v:7d} rows")


if __name__ == "__main__":
    main()
