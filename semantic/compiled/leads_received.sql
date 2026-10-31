-- metric: leads_received (Leads received)
SELECT tenant_id AS tenant_id,
       toStartOfMonth(received_at) AS month,
       count() AS value,
       count() AS rows_used
FROM marts.fct_leads
GROUP BY tenant_id, month
ORDER BY tenant_id, month
