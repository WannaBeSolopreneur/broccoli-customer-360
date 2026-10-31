-- metric: completed_revenue (Completed job revenue (all sources))
SELECT tenant_id AS tenant_id,
       toStartOfMonth(created_on) AS month,
       sum(toFloat64(total_revenue)) AS value,
       count() AS rows_used
FROM marts.fct_jobs
WHERE (status = 'Completed')
GROUP BY tenant_id, month
ORDER BY tenant_id, month
