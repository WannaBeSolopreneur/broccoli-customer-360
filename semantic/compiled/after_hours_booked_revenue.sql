-- metric: after_hours_booked_revenue (Revenue the AI booked after hours)
SELECT tenant_id AS tenant_id,
       toStartOfMonth(created_on) AS month,
       sum(toFloat64(total_revenue)) AS value,
       count() AS rows_used
FROM marts.fct_jobs
WHERE (booked_by_broccoli)
  AND (status = 'Completed')
  AND (booked_after_hours)
GROUP BY tenant_id, month
ORDER BY tenant_id, month
