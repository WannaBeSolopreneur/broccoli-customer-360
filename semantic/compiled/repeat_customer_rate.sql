-- metric: repeat_customer_rate (Repeat customer rate)
SELECT tenant_id AS tenant_id,
       toStartOfMonth(first_seen_at) AS month,
       (countIf(completed_jobs >= 2)) / nullIf(countIf(completed_jobs >= 1), 0) AS value,
       countIf(completed_jobs >= 2) AS numerator,
       countIf(completed_jobs >= 1) AS denominator,
       count() AS rows_used
FROM marts.dim_customer
GROUP BY tenant_id, month
ORDER BY tenant_id, month
