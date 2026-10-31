-- metric: booked_revenue (Booked revenue from Broccoli)
SELECT tenant_id AS tenant_id,
       toStartOfMonth(created_on) AS month,
       sum(toFloat64(total_revenue)) AS value,
       count() AS rows_used
FROM marts.fct_jobs
WHERE (booked_by_broccoli)
  AND (status = 'Completed')
GROUP BY tenant_id, month
ORDER BY tenant_id, month
