-- Staging layer. One clean, typed table per source. No joins here.
CREATE DATABASE IF NOT EXISTS stg;

CREATE OR REPLACE TABLE stg.calls ENGINE = MergeTree ORDER BY (tenant_id, call_id) AS
SELECT tenant_id, call_id,
       c360_ts(started_at) AS started_at,
       direction, channel,
       customer_phone AS phone_raw,
       c360_e164(customer_phone) AS phone_e164,
       answered_by, outcome, intent,
       booked = 'true' AS booked,
       toUInt32OrZero(duration_sec) AS duration_sec,
       nullIf(lead_external_id, '') AS lead_external_id,
       nullIf(caller_name, '') AS caller_name,
       c360_ts(_loaded_at) AS _loaded_at
FROM raw.calls;

CREATE OR REPLACE TABLE stg.leads ENGINE = MergeTree ORDER BY (tenant_id, lead_row_id) AS
SELECT l.tenant_id AS tenant_id, lead_row_id,
       c360_ts(received_at) AS received_at,
       JSONExtractString(payload, 'providerId') AS provider_id,
       nullIf(JSONExtractString(payload, 'externalLeadId'), '') AS external_lead_id,
       JSONExtractString(payload, 'customer', 'phone') AS phone_raw,
       c360_e164(JSONExtractString(payload, 'customer', 'phone')) AS phone_e164,
       c360_email(JSONExtractString(payload, 'customer', 'email')) AS email,
       if(JSONHas(payload, 'customer', 'name'), JSONExtractString(payload, 'customer', 'name'),
          concat(JSONExtractString(payload, 'customer', 'firstName'), ' ', JSONExtractString(payload, 'customer', 'lastName'))) AS full_name,
       if(JSONType(payload, 'address') = 'Object', JSONExtractString(payload, 'address', 'street'),
          trimBoth(splitByChar(',', JSONExtractString(payload, 'address'))[1])) AS street,
       if(JSONType(payload, 'address') = 'Object', JSONExtractString(payload, 'address', 'postalCode'),
          JSONExtractString(payload, 'address')) AS zip_source,
       nullIf(JSONExtractString(payload, 'serviceType'), '') AS service_type,
       nullIf(JSONExtractString(payload, 'source'), '') AS lead_source,
       ifNull(nullIf(JSONExtractString(payload, 'preferredChannel'), ''), 'CONFIG_DEFAULT') AS preferred_channel,
       c360_ts(_loaded_at) AS _loaded_at
FROM raw.leads AS l;

CREATE OR REPLACE TABLE stg.jobs ENGINE = MergeTree ORDER BY (tenant_id, job_id) AS
SELECT tenant_id, job_id, job_number, st_customer_id,
       customer_name AS full_name,
       c360_e164(customer_phone) AS phone_e164,
       c360_email(customer_email) AS email,
       location_street AS street, location_zip AS zip_source,
       business_unit, job_type, booking_source,
       startsWith(booking_source, 'broccoli') AS booked_by_broccoli,
       nullIf(broccoli_ref, '') AS broccoli_ref,
       c360_ts(created_on) AS created_on,
       c360_ts(scheduled_start) AS scheduled_start,
       status,
       c360_ts(completed_on) AS completed_on,
       toDecimal64OrZero(total_revenue, 2) AS total_revenue,
       c360_ts(_loaded_at) AS _loaded_at
FROM raw.jobs;

CREATE OR REPLACE TABLE stg.invoices ENGINE = MergeTree ORDER BY (tenant_id, invoice_id) AS
SELECT tenant_id, invoice_id, invoice_number, invoice_type,
       nullIf(job_number, '') AS job_number,
       bill_to_name AS full_name,
       c360_email(bill_to_email) AS email,
       c360_e164(bill_to_phone) AS phone_e164,
       trimBoth(splitByChar(',', bill_to_address)[1]) AS street,
       bill_to_address AS zip_source,
       nullIf(membership_id, '') AS membership_id,
       toDateOrNull(membership_period_start) AS membership_period_start,
       toDateOrNull(membership_period_end) AS membership_period_end,
       c360_ts(invoice_date) AS invoice_date,
       c360_ts(due_date) AS due_date,
       toDecimal64OrZero(amount, 2) AS amount,
       toDecimal64OrZero(amount_paid, 2) AS amount_paid,
       status,
       c360_ts(_loaded_at) AS _loaded_at
FROM raw.invoices;

CREATE OR REPLACE TABLE stg.tickets ENGINE = MergeTree ORDER BY (tenant_id, ticket_id) AS
SELECT tenant_id, ticket_id,
       c360_ts(created_at) AS created_at,
       channel,
       requester_name AS full_name,
       c360_email(requester_email) AS email,
       c360_e164(requester_phone) AS phone_e164,
       category, status,
       c360_ts(resolved_at) AS resolved_at,
       toUInt8OrNull(csat) AS csat,
       c360_ts(_loaded_at) AS _loaded_at
FROM raw.tickets;
