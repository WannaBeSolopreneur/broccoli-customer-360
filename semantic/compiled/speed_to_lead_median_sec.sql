-- metric: speed_to_lead_median_sec (Speed to lead (median seconds))
SELECT tenant_id AS tenant_id,
       toStartOfMonth(received_at) AS month,
       quantileExact(0.5)(speed_to_lead_sec) AS value,
       count() AS rows_used
FROM marts.fct_leads
WHERE (first_contact_at IS NOT NULL)
GROUP BY tenant_id, month
ORDER BY tenant_id, month
