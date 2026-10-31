-- Landing layer. Files are read as they are, every column as text.
-- tenant_id comes from the file name, so one file per tenant per source.
CREATE DATABASE IF NOT EXISTS raw;

CREATE OR REPLACE TABLE raw.calls ENGINE = MergeTree ORDER BY (tenant_id, call_id) AS
SELECT replaceRegexpOne(_file, '\\.csv$', '') AS tenant_id, *
FROM file('{{RAW}}/calls/*.csv', 'CSVWithNames',
  'call_id String, started_at String, direction String, channel String, customer_phone String, answered_by String, outcome String, intent String, booked String, duration_sec String, lead_external_id String, caller_name String, _loaded_at String');

CREATE OR REPLACE TABLE raw.leads ENGINE = MergeTree ORDER BY (tenant_id, lead_row_id) AS
SELECT replaceRegexpOne(_file, '\\.jsonl$', '') AS tenant_id,
       JSONExtractString(json, 'lead_row_id') AS lead_row_id,
       JSONExtractString(json, 'received_at') AS received_at,
       JSONExtractString(json, '_loaded_at') AS _loaded_at,
       JSONExtractRaw(json, 'payload') AS payload
FROM file('{{RAW}}/leads/*.jsonl', 'JSONAsString');

CREATE OR REPLACE TABLE raw.jobs ENGINE = MergeTree ORDER BY (tenant_id, job_id) AS
SELECT replaceRegexpOne(_file, '\\.csv$', '') AS tenant_id, *
FROM file('{{RAW}}/jobs/*.csv', 'CSVWithNames',
  'job_id String, job_number String, st_customer_id String, customer_name String, customer_phone String, customer_email String, location_street String, location_city String, location_state String, location_zip String, business_unit String, job_type String, booking_source String, broccoli_ref String, created_on String, scheduled_start String, status String, completed_on String, total_revenue String, _loaded_at String');

CREATE OR REPLACE TABLE raw.invoices ENGINE = MergeTree ORDER BY (tenant_id, invoice_id) AS
SELECT replaceRegexpOne(_file, '\\.csv$', '') AS tenant_id, *
FROM file('{{RAW}}/invoices/*.csv', 'CSVWithNames',
  'invoice_id String, invoice_number String, invoice_type String, job_number String, bill_to_name String, bill_to_email String, bill_to_phone String, bill_to_address String, membership_id String, membership_period_start String, membership_period_end String, invoice_date String, due_date String, amount String, amount_paid String, status String, _loaded_at String');

CREATE OR REPLACE TABLE raw.tickets ENGINE = MergeTree ORDER BY (tenant_id, ticket_id) AS
SELECT replaceRegexpOne(_file, '\\.csv$', '') AS tenant_id, *
FROM file('{{RAW}}/tickets/*.csv', 'CSVWithNames',
  'ticket_id String, created_at String, channel String, requester_name String, requester_email String, requester_phone String, category String, status String, resolved_at String, csat String, _loaded_at String');

CREATE OR REPLACE TABLE raw.tenants ENGINE = MergeTree ORDER BY tenant_id AS
SELECT * FROM file('{{RAW}}/tenants.json', 'JSONEachRow',
  'tenant_id String, name String, trade String, city String, state String, utc_offset Int32, provider_id String');
