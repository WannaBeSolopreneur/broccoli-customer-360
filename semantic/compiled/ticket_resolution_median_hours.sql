-- metric: ticket_resolution_median_hours (Support resolution time (median hours))
SELECT tenant_id AS tenant_id,
       toStartOfMonth(created_at) AS month,
       quantileExact(0.5)(resolution_hours) AS value,
       count() AS rows_used
FROM marts.fct_tickets
WHERE (resolution_hours IS NOT NULL)
GROUP BY tenant_id, month
ORDER BY tenant_id, month
