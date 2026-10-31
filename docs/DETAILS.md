# Details

This page explains how the project works, what the numbers are, and where it falls short.
All numbers come from the files in `reports/` after `make all`. All data is synthetic.

## 1. Layout

| Folder | What is in it |
|---|---|
| `c360/generate.py` | Seeded synthetic data. Same seed, same bytes. |
| `models/` | SQL for each layer, plus `schema.yml` with docs and tests. |
| `c360/er.py` | Entity resolution and the stable key registry. |
| `semantic/metrics.yml` | The 12 metric definitions. `semantic/compiled/` holds the SQL made from them. |
| `c360/quality.py` | Freshness, column tests and row count checks. Writes `reports/alerts.json`. |
| `c360/ask.py` | Plain English question to metric. |
| `c360/row_policies.py` | Row policy test on a real ClickHouse server. |
| `api_leads/` | Appendix. An OpenAPI file and a validator for the API Leads webhook. |
| `tests/`, `api_leads/tests/` | The pytest suite. |
| `ci/ci.yml` | A GitHub Actions workflow. It is kept outside `.github/` so it does not run yet. |

## 2. The synthetic data

Three made up contractors. Alpine Comfort HVAC in Denver, Bayside Plumbing and Drain in Oakland, Lone Star Electric in Austin. The window is April to September 2026. The "as of" time is 2026-10-01 06:00 UTC.

Five sources per tenant:

- Calls. Inbound calls the AI agent answered, outbound lead follow ups, and spam.
- API leads. JSON payloads in the shape of the API Leads docs. Partners retry, so about 8% repeat an `externalLeadId`.
- Jobs. ServiceTitan style. Some customers exist twice in the field service system.
- Invoices. Service invoices and memberships.
- Support tickets.

The mess is on purpose. Phones come in many formats, and each tenant's carrier logs a different one. Emails change case and gain spaces. Names have typos and nicknames. Addresses have unit numbers, short and long street types, and zip+4 or no zip. About 10% of people share a home with family, sometimes with a shared landline. About 4% of people are customers of more than one tenant.

The generator also writes `data/ground_truth/identity_truth.csv`. It says which real person made each record. The pipeline never reads it. Only the scoring step does.

## 3. Warehouse layers

1. `raw`. Files read as they are. Every column is a string.
2. `stg`. Typed and cleaned. Phones go to E.164. Emails go to lower case. Streets go to a standard key.
3. `er`. One identity record per source row, the match edges, and the final map from record to `customer_key`.
4. `marts`. `dim_customer` and six fact tables: calls, leads, jobs, invoices, tickets, memberships.
5. `metrics`. One view per metric at tenant and month grain.
6. `tenant_api` and `benchmarks`. What a customer facing app would read.

### Why chDB and not dbt

The job post says ClickHouse, so the SQL is ClickHouse SQL. I ran it with chDB, which is ClickHouse inside Python. It needs no server, so `make all` works on any laptop.

dbt-clickhouse needs a running server, so I did not use it here. The layout copies dbt ideas instead. SQL files per layer, a `schema.yml` with docs and tests, and freshness rules per source. Moving to dbt on a real ClickHouse cluster would be mostly file renames.

chDB does not allow `CREATE USER` or `CREATE ROW POLICY`. So the row policy test starts a real ClickHouse server for a few seconds. See section 6.

## 4. Entity resolution

### Rules

Records only match inside one tenant. Each rule makes an edge between two records.

| Rule | Match when |
|---|---|
| phone | Same E.164 phone. Spam and outbound calls are left out before matching. |
| email | Same cleaned email. |
| st_customer_id | Two jobs share a ServiceTitan customer id. |
| external_lead_id | Two leads share an `externalLeadId`, as with partner retries. |
| invoice_job | An invoice and a job share a job number. |
| fuzzy_name_address | Same house number, street names close (ngram distance 0.35 or less), zips agree or one is missing, last names close (Jaro Winkler 0.92 or more), and first names close (0.90 or more). A first name that is only an initial matches the same initial. Nicknames map to formal names first, so Bob matches Robert. |

Edges become groups with label propagation, run as SQL in ClickHouse. It took 7 rounds on this data.

### Stable keys

Each group gets a `customer_key` like `cus_` plus 16 hex characters. The registry at `warehouse/state/key_registry.csv` remembers which record had which key.

- A rebuild gives every customer the same key. A test checks this.
- If two old customers turn out to be one person, the older key wins. The other key is logged in `er.key_merges` so dashboards can follow it.
- A new key is never one that the registry already gave someone else. A test checks this too. An early version had this bug. It showed up as a gap between the ablation score and the final score, and the test now guards it.

### Scores

Pairwise scores against the hidden truth, inside each tenant.

| Rules used | Precision | Recall | F1 |
|---|---|---|---|
| Phone only | 99.3% | 84.0% | 91.0% |
| + Email | 98.1% | 95.7% | 96.8% |
| + System ids | 97.9% | 98.1% | 98.0% |
| + Fuzzy name and address (final) | 97.2% | 98.9% | 98.0% |

Final run: 22,357 records, 5,560 true people, 5,708 predicted customers. 96.35% of people end up in exactly one customer. 51 customers mix two or more people. 0 keys span two tenants.

### Where it goes wrong

Wrong edges by rule in the final run:

| Rule | Edges | Wrong edges |
|---|---|---|
| phone | 15,207 | 90 |
| fuzzy_name_address | 22,141 | 39 |
| email | 7,143 | 22 |
| st_customer_id, external_lead_id, invoice_job | 6,051 | 0 |

- Phone. A family shares a landline, so two people look like one.
- Fuzzy. Family members at one address with the same last name and a first initial only.
- Email. A few people share a work email.

Next steps I would try: treat a phone seen with many names as a household phone, and stop chains of weak edges from merging two strong groups.

## 5. Metrics

`semantic/metrics.yml` holds 12 metrics. Each has a label, a plain description, the model and time column, a type, a format, synonyms and the allowed dimensions.

Types are count, sum, avg, median, count distinct and ratio. A ratio is total numerator over total denominator. It is never an average of rates. A test checks this for every ratio metric.

The compiler only accepts known dimensions and safe values. Everything else raises an error.

Notes on a few values, so nobody reads them as findings:

- Alpine's median speed to lead is 27 seconds. Bayside is 858 and Lone Star is 811. This is a generator setting. Alpine lets the AI agent reach out after hours, and the others wait until 8am.
- Lead to booking rate uses the resolved customer and a 14 day window.

## 6. Tenant isolation

Three layers.

1. Every mart has `tenant_id`. Customer facing reads go through `tenant_api.*`. These are parameterized views, for example `tenant_api.fct_leads(tenant_id='tnt_alpine')`. Tests check every table for every tenant, an unknown tenant, and an injection attempt.
2. On a ClickHouse server, `models/security/02_row_policies.sql` adds one reader user and one row policy per tenant per table. The test loads the marts into a temporary local server, version 26.10.3.7. It checks 21 tenant and table pairs. Each user sees only its own rows, even with a filter asking for other tenants. A wrong password is rejected. The server only listens on 127.0.0.1 and is deleted after.
3. Benchmarks. `benchmarks.metric_benchmarks` has no `tenant_id` column. A tenant reads `tenant_api.my_benchmarks`, which shows its own value next to the peer numbers.

Benchmark rules, set in `metrics.yml`:

- Fewer than 3 tenants: no benchmark at all.
- 3 or 4 tenants: only the average of tenant values. A median of 3 values is one tenant's exact number, so it is hidden.
- 5 or more tenants: median, p25 and p75 as well.

Known limit. With 3 tenants, one tenant can work out the average of the other two. For real use I would raise the minimum or add noise.

## 7. Quality checks

`make quality` runs 74 checks. Errors fail the run. Warnings only report.

- Freshness for each raw source and tenant, against the as of time. Calls and leads warn after 2 hours and error after 6. Jobs warn after 6 and error after 24. Invoices and tickets warn after 12 and error after 36.
- Not null, unique, accepted values, and links between tables, all from `schema.yml`.
- Row counts that must survive each layer, so nothing is dropped or doubled.
- No event after the as of time, and no customer key in two tenants.

Failed checks go to `reports/alerts.json`. In real use that list would go to Slack or PagerDuty. Nothing is sent from this repo.

Tests prove the alerts fire. One moves the clock forward a day, which makes the feeds stale. Another adds a row with an unknown tenant and a missing customer.

## 8. Ask

`make ask` runs 10 sample questions. A question becomes a plan: one metric, an optional tenant, an optional month and a breakdown. The SQL comes from the compiler, never from the question.

It uses keyword matching, not a language model. The point is the contract. An AI agent should pick from defined metrics in the same way, so people and agents get the same number.

## 9. API Leads appendix

`api_leads/openapi.yaml` is an OpenAPI 3.1 description of the API Leads webhook. I wrote it by hand from https://docs.broccoli.com/api-leads/specification on 2026-10-31. Where the page is silent, the file is silent too. Nothing was sent to the live API.

`api_leads/validator.py` checks a payload offline. It uses the request schema from the OpenAPI file plus the rules a schema cannot say alone, such as the UUID check. It flags reserved `additionalContext` keys and a missing `externalLeadId` as warnings, since the docs say those do not fail a request. A test runs every synthetic lead in this repo through it.

Notes from reading the docs site on 2026-10-31:

- https://docs.broccoli.com/llms.txt returned 404.
- https://docs.broccoli.com/llms-full.txt returned 200. It held only the "Send a test request" page.
- I did not find a published OpenAPI file. `/openapi.json` and `/api-reference/openapi.json` returned 404.

## 10. Limits

- It is a demo on about 30,000 synthetic rows. I have not tuned it for event scale. On real data I would add materialized views for the metric views and partition the facts by month.
- Entity resolution rebuilds in full each time. With more data I would match only new records against existing customers.
- The ask tool only knows the words in the synonyms list.
- The CI file is saved in `ci/` and has not run on GitHub.
