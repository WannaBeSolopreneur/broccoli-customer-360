-- One row per source record that carries a person's identity.
-- Spam calls and our own outbound calls are left out on purpose.
CREATE DATABASE IF NOT EXISTS er;

CREATE OR REPLACE TABLE er.identity_records ENGINE = MergeTree ORDER BY (tenant_id, record_key) AS
WITH src AS (
    SELECT tenant_id, 'calls' AS source, call_id AS record_id,
           CAST(phone_e164 AS Nullable(String)) AS phone_e164, CAST(NULL AS Nullable(String)) AS email,
           CAST(caller_name AS Nullable(String)) AS full_name, CAST(NULL AS Nullable(String)) AS street,
           CAST(NULL AS Nullable(String)) AS zip_source, CAST(NULL AS Nullable(String)) AS st_customer_id,
           CAST(NULL AS Nullable(String)) AS job_number, CAST(NULL AS Nullable(String)) AS external_lead_id,
           started_at AS seen_at
    FROM stg.calls WHERE direction = 'inbound' AND outcome != 'spam'
    UNION ALL
    SELECT tenant_id, 'leads', lead_row_id, phone_e164, email, full_name, street, zip_source,
           NULL, NULL, external_lead_id, received_at
    FROM stg.leads
    UNION ALL
    SELECT tenant_id, 'jobs', job_id, phone_e164, email, full_name, street, zip_source,
           st_customer_id, job_number, NULL, created_on
    FROM stg.jobs
    UNION ALL
    SELECT tenant_id, 'invoices', invoice_id, phone_e164, email, full_name, street, zip_source,
           NULL, job_number, NULL, invoice_date
    FROM stg.invoices
    UNION ALL
    SELECT tenant_id, 'tickets', ticket_id, phone_e164, email, full_name, NULL, NULL,
           NULL, NULL, NULL, created_at
    FROM stg.tickets
)
SELECT tenant_id,
       concat(tenant_id, '|', source, ':', record_id) AS record_key,
       source, record_id, phone_e164, email,
       c360_clean_token(c360_first_raw(full_name)) AS first_token,
       transform(ifNull(first_token, ''), {{NICK_FROM}}, {{NICK_TO}}, ifNull(first_token, '')) AS first_name,
       c360_clean_token(c360_last_raw(full_name)) AS last_name,
       c360_street_key(street) AS street_key,
       c360_house_number(street) AS house_number,
       c360_zip5(zip_source) AS zip5,
       st_customer_id, job_number, external_lead_id, seen_at
FROM src;
