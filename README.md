# Customer 360 for Broccoli

Hi Broccoli team, I built this to show how I would approach your Founding Data Engineer role.

Live demo: https://wannabesolopreneur.github.io/broccoli-customer-360-demo/

It is a small, working version of the data layer in your job post. It runs on ClickHouse. One command builds it all and tests it.

The data is 10 made up contractors and about 305,000 rows over 12 months. It covers HVAC, plumbing, electrical and roofing in 10 cities.

## About me

- I am a Data Scientist at DataQHealth.
- I build healthcare data pipelines that process 10M+ records a year. They cover claims, encounters and patient attribution.
- Matching the same patient across sources is the same problem as matching a homeowner across calls, billing and support.
- I work with CMS data. I automated our ACO work, and the ACO was approved in under 3 months.
- I built a FHIR AI scribe.
- I built an NLP tool for heart device alerts. It saves nurses 3 hours a day.
- MS in Business Analytics and AI, UT Dallas. BSc in Physics, University of Nottingham.
- GitHub: https://github.com/WannaBeSolopreneur
- LinkedIn: https://www.linkedin.com/in/asad-moulvi-aaa278175

## What your job post asks for, and what I built

| Your job post | What I built |
|---|---|
| Pipelines into ClickHouse | Five messy sources load into ClickHouse in layers. Raw, then staging, then clean tables. |
| Entity resolution across billing, support and calls | Six matching rules link 241,554 records into one `customer_key` per person. Keys stay the same on every rebuild. |
| Clean, documented tables | `dim_customer` and six fact tables. Every column is described in `models/schema.yml`, and the text is copied into ClickHouse comments. |
| Source of truth library | `semantic/metrics.yml` defines 16 metrics once. All metric SQL is made from that file. |
| Human and AI ready | `make ask` answers 15 plain English questions. Each one maps to a defined metric, never to new SQL. |
| Freshness checks, tests and alerts | 109 checks per build. A stale feed or bad row writes an alert before anyone sees a wrong number. |
| Customer dashboards and benchmarks | Every table has `tenant_id`. Tenants read through views that only return their own rows. Peer benchmarks show aggregates only, and only for groups of 5 or more contractors. |
| Strict customer data isolation | A test starts a real ClickHouse server, adds one user and row policy per tenant, and proves no tenant sees another. It checks 70 tenant and table pairs. |
| ServiceTitan style field service data | Calls, API leads, jobs, invoices, memberships and support tickets. |

## How it fits together

![Architecture](docs/img/architecture.png)

## Results from the last run

These numbers come from `reports/`. The data is synthetic, so they show the method works. They are not claims about real customers.

Entity resolution, scored against the hidden ground truth:

- Precision 98.0%. Of the record pairs I joined, this share really are the same person.
- Recall 99.0%. Of the record pairs that are the same person, this share I joined.
- F1 98.5%.
- 241,554 records became 48,567 customers. The truth is 47,033 people.
- 0 customers span two tenants.

![Entity resolution](docs/img/entity_resolution.png)

Here is one person from the run. `make example` prints it. Donna Silva shows up 12 times in 5 systems. Her first name is written 4 ways (Donna, Dona, Donnna and D.). Her phone is written 5 ways and her email changes case. One lead came in twice, because the partner sent it again. All 12 records end up as one customer.

Why it matters. If you link a lead to a job only by the lead id, you miss bookings. Across all 25,130 leads, lead id only finds 25.8% booked. With entity resolution it is 44.2%. The hidden truth is 44.2%. In this data, a job booked from a lead carries the lead id only 60% of the time. That is a generator setting, not a real number. It is why the lead id only number is lower.

![Lead to booking](docs/img/lead_booking.png)

Peer benchmarks. With 10 contractors, each one can see where it stands. It sees its own value and the peer median, p25 and p75. It never sees another contractor's number. For example, Alpine's lead to booking rate is 45.5% and the peer median is 43.6%. A peer group under 5 contractors shows nothing.

A few more answers from `make ask`:

- Desert Air: $8,078,783 of revenue the AI booked after hours, when the office was closed.
- Alpine: by lead source, Google LSA books 55.5% of leads and Meta ads books 35.2%.
- Alpine: 171 repeat customers that only matching finds. No single ServiceTitan customer id holds two of their jobs.

## Quick start

You need Python 3.11 or newer and `make`.

```
make setup
make all
```

`make all` took 64 seconds on my last run. It makes the data, builds the warehouse, runs 109 checks and 123 tests, and writes the charts.

Try a question:

```
make ask
.venv/bin/python -m c360.ask "Compare lead conversion for each contractor"
```

See one messy customer joined into one:

```
make example
```

The row policy test needs a ClickHouse binary. Set `CLICKHOUSE_BIN` to its path. Without it, that one test is skipped.

## All data is synthetic

Every person, phone, email, address and company here is made up by `c360/generate.py`. Phones use 555 numbers. Emails use example domains. No real data was used.

## More detail

Design choices, matching rules, error cases and known limits are in [docs/DETAILS.md](docs/DETAILS.md).
