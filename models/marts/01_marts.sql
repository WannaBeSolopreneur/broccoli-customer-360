-- Marts. Clean fact tables, every row tied to a tenant and a customer_key.
CREATE DATABASE IF NOT EXISTS marts;

CREATE OR REPLACE TABLE marts.fct_jobs ENGINE = MergeTree ORDER BY (tenant_id, job_id) AS
SELECT j.tenant_id AS tenant_id, j.job_id AS job_id, j.job_number AS job_number, m.customer_key AS customer_key,
       j.st_customer_id AS st_customer_id, j.business_unit AS business_unit, j.job_type AS job_type,
       j.booking_source AS booking_source, j.booked_by_broccoli AS booked_by_broccoli, j.broccoli_ref AS broccoli_ref,
       j.created_on AS created_on, j.scheduled_start AS scheduled_start, j.status AS status,
       j.completed_on AS completed_on, j.total_revenue AS total_revenue,
       NOT (toHour(j.created_on + toIntervalHour(t.utc_offset)) BETWEEN 8 AND 19) AS booked_after_hours,
       j._loaded_at AS _loaded_at
FROM stg.jobs AS j
LEFT JOIN er.identity_map AS m ON m.record_key = concat(j.tenant_id, '|jobs:', j.job_id)
LEFT JOIN raw.tenants AS t ON t.tenant_id = j.tenant_id;

CREATE OR REPLACE TABLE marts.fct_leads ENGINE = MergeTree ORDER BY (tenant_id, lead_row_id) AS
WITH ranked AS (
    SELECT l.*, m.customer_key AS customer_key,
           row_number() OVER (PARTITION BY l.tenant_id, l.provider_id, l.external_lead_id ORDER BY l.received_at, l.lead_row_id) AS rn,
           count() OVER (PARTITION BY l.tenant_id, l.provider_id, l.external_lead_id) AS sends
    FROM stg.leads AS l
    LEFT JOIN er.identity_map AS m ON m.record_key = concat(l.tenant_id, '|leads:', l.lead_row_id)
),
firsts AS (SELECT * FROM ranked WHERE rn = 1),
contact AS (
    SELECT tenant_id, lead_external_id, min(started_at) AS first_contact_at,
           countIf(outcome IN ('booked', 'not_interested')) > 0 AS connected
    FROM stg.calls WHERE direction = 'outbound' AND lead_external_id IS NOT NULL
    GROUP BY tenant_id, lead_external_id
),
booked AS (
    SELECT f.tenant_id AS tenant_id, f.external_lead_id AS external_lead_id,
           argMin(j.job_id, j.created_on) AS booked_job_id, min(j.created_on) AS booked_at
    FROM firsts AS f
    INNER JOIN marts.fct_jobs AS j ON j.tenant_id = f.tenant_id AND j.customer_key = f.customer_key
    WHERE j.created_on >= f.received_at AND j.created_on < f.received_at + INTERVAL 14 DAY
    GROUP BY f.tenant_id, f.external_lead_id
),
by_ref AS (
    SELECT tenant_id, broccoli_ref AS external_lead_id, 1 AS hit
    FROM marts.fct_jobs WHERE broccoli_ref IS NOT NULL GROUP BY tenant_id, broccoli_ref
)
SELECT f.tenant_id AS tenant_id, f.provider_id AS provider_id, f.external_lead_id AS external_lead_id,
       f.lead_row_id AS lead_row_id, f.customer_key AS customer_key, f.received_at AS received_at,
       f.lead_source AS lead_source, f.service_type AS service_type, f.preferred_channel AS preferred_channel,
       toUInt32(f.sends - 1) AS duplicate_sends,
       c.first_contact_at AS first_contact_at,
       if(c.first_contact_at IS NULL, NULL, dateDiff('second', f.received_at, c.first_contact_at)) AS speed_to_lead_sec,
       toHour(f.received_at + toIntervalHour(t.utc_offset)) BETWEEN 8 AND 19 AS received_in_hours,
       ifNull(c.connected, false) AS connected,
       b.booked_job_id AS booked_job_id, b.booked_at AS booked_at,
       b.booked_job_id IS NOT NULL AS booked_within_14d,
       ifNull(r.hit, 0) = 1 AS booked_by_ref_only,
       f._loaded_at AS _loaded_at
FROM firsts AS f
LEFT JOIN contact AS c ON c.tenant_id = f.tenant_id AND c.lead_external_id = f.external_lead_id
LEFT JOIN booked AS b ON b.tenant_id = f.tenant_id AND b.external_lead_id = f.external_lead_id
LEFT JOIN by_ref AS r ON r.tenant_id = f.tenant_id AND r.external_lead_id = f.external_lead_id
LEFT JOIN raw.tenants AS t ON t.tenant_id = f.tenant_id;

CREATE OR REPLACE TABLE marts.fct_calls ENGINE = MergeTree ORDER BY (tenant_id, call_id) AS
SELECT c.tenant_id AS tenant_id, c.call_id AS call_id,
       if(c.direction = 'inbound', m.customer_key, l.customer_key) AS customer_key,
       c.started_at AS started_at, c.direction AS direction, c.channel AS channel, c.phone_e164 AS phone_e164,
       c.answered_by AS answered_by, c.outcome AS outcome, c.intent AS intent, c.booked AS booked,
       c.duration_sec AS duration_sec, c.lead_external_id AS lead_external_id,
       c.outcome = 'spam' AS is_spam, c._loaded_at AS _loaded_at
FROM stg.calls AS c
LEFT JOIN er.identity_map AS m ON m.record_key = concat(c.tenant_id, '|calls:', c.call_id)
LEFT JOIN marts.fct_leads AS l ON l.tenant_id = c.tenant_id AND l.external_lead_id = c.lead_external_id;

CREATE OR REPLACE TABLE marts.fct_invoices ENGINE = MergeTree ORDER BY (tenant_id, invoice_id) AS
SELECT i.tenant_id AS tenant_id, i.invoice_id AS invoice_id, i.invoice_number AS invoice_number,
       m.customer_key AS customer_key, i.invoice_type AS invoice_type, j.job_id AS job_id,
       i.membership_id AS membership_id, i.membership_period_start AS membership_period_start,
       i.membership_period_end AS membership_period_end, i.invoice_date AS invoice_date, i.due_date AS due_date,
       i.amount AS amount, i.amount_paid AS amount_paid, i.status AS status, i._loaded_at AS _loaded_at
FROM stg.invoices AS i
LEFT JOIN er.identity_map AS m ON m.record_key = concat(i.tenant_id, '|invoices:', i.invoice_id)
LEFT JOIN stg.jobs AS j ON j.tenant_id = i.tenant_id AND j.job_number = i.job_number;

CREATE OR REPLACE TABLE marts.fct_tickets ENGINE = MergeTree ORDER BY (tenant_id, ticket_id) AS
SELECT t.tenant_id AS tenant_id, t.ticket_id AS ticket_id, m.customer_key AS customer_key,
       t.created_at AS created_at, t.channel AS channel, t.category AS category, t.status AS status,
       t.resolved_at AS resolved_at,
       if(t.resolved_at IS NULL, NULL, dateDiff('minute', t.created_at, t.resolved_at) / 60.0) AS resolution_hours,
       t.csat AS csat, t._loaded_at AS _loaded_at
FROM stg.tickets AS t
LEFT JOIN er.identity_map AS m ON m.record_key = concat(t.tenant_id, '|tickets:', t.ticket_id);

-- A membership counts as renewed when the same customer starts a new
-- membership within 45 days of the old one ending. The billing system gives
-- renewals a new membership_id, so this needs the resolved customer_key.
CREATE OR REPLACE TABLE marts.fct_memberships ENGINE = MergeTree ORDER BY (tenant_id, membership_id)
SETTINGS allow_nullable_key = 1 AS
WITH m AS (
    SELECT tenant_id, membership_id, customer_key, membership_period_start AS period_start,
           membership_period_end AS period_end, amount, invoice_date
    FROM marts.fct_invoices WHERE invoice_type = 'membership'
)
SELECT a.tenant_id AS tenant_id, a.membership_id AS membership_id, a.customer_key AS customer_key,
       a.period_start AS period_start, a.period_end AS period_end, a.amount AS amount,
       a.period_end <= toDate('{{AS_OF}}') AS renewal_due,
       countIf(b.membership_id IS NOT NULL AND b.membership_id != a.membership_id
               AND b.period_start > a.period_start
               AND b.period_start BETWEEN a.period_end - 45 AND a.period_end + 45) > 0 AS renewed
FROM m AS a
LEFT JOIN m AS b ON a.tenant_id = b.tenant_id AND a.customer_key = b.customer_key
GROUP BY a.tenant_id, a.membership_id, a.customer_key, a.period_start, a.period_end, a.amount;

CREATE OR REPLACE TABLE marts.dim_customer ENGINE = MergeTree ORDER BY (tenant_id, customer_key)
SETTINGS allow_nullable_key = 1 AS
WITH r AS (
    SELECT m.tenant_id AS tenant_id, m.customer_key AS customer_key, r.source AS source,
           r.phone_e164 AS phone_e164, r.email AS email, r.first_name AS first_name, r.last_name AS last_name,
           r.street_key AS street_key, r.zip5 AS zip5, r.seen_at AS seen_at
    FROM er.identity_map AS m INNER JOIN er.identity_records AS r ON r.record_key = m.record_key
),
jobs AS (
    -- Completed jobs per customer, and the most any one ServiceTitan customer id holds.
    -- A repeat customer that the field service system splits across ids shows up here.
    SELECT tenant_id, customer_key, sum(n) AS completed_jobs, max(n) AS max_jobs_one_st_id
    FROM (SELECT tenant_id, customer_key, st_customer_id, count() AS n
          FROM marts.fct_jobs WHERE status = 'Completed' GROUP BY tenant_id, customer_key, st_customer_id)
    GROUP BY tenant_id, customer_key
),
agg AS (
SELECT r.tenant_id AS tenant_id, r.customer_key AS customer_key,
       topKIf(1)(concat(initcap(first_name), ' ', initcap(ifNull(last_name, ''))),
                 length(first_name) > 1 AND last_name IS NOT NULL)[1] AS display_name,
       topKIf(1)(assumeNotNull(phone_e164), phone_e164 IS NOT NULL)[1] AS primary_phone,
       topKIf(1)(assumeNotNull(email), email IS NOT NULL)[1] AS primary_email,
       topKIf(1)(assumeNotNull(street_key), street_key IS NOT NULL)[1] AS street_key,
       topKIf(1)(assumeNotNull(zip5), zip5 IS NOT NULL)[1] AS zip5,
       uniqExactIf(phone_e164, phone_e164 IS NOT NULL) AS phone_count,
       uniqExactIf(email, email IS NOT NULL) AS email_count,
       arraySort(groupUniqArray(source)) AS sources,
       count() AS record_count,
       min(seen_at) AS first_seen_at,
       max(seen_at) AS last_seen_at
FROM r GROUP BY r.tenant_id, r.customer_key
)
SELECT agg.*, toUInt64(ifNull(jobs.completed_jobs, 0)) AS completed_jobs,
       toUInt64(ifNull(jobs.max_jobs_one_st_id, 0)) AS max_jobs_one_st_id
FROM agg LEFT JOIN jobs ON jobs.tenant_id = agg.tenant_id AND jobs.customer_key = agg.customer_key;
