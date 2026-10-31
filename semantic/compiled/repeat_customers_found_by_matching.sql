-- metric: repeat_customers_found_by_matching (Repeat customers found only by matching)
SELECT tenant_id AS tenant_id,
       toStartOfMonth(first_seen_at) AS month,
       count() AS value,
       count() AS rows_used
FROM marts.dim_customer
WHERE (completed_jobs >= 2)
  AND (max_jobs_one_st_id < 2)
GROUP BY tenant_id, month
ORDER BY tenant_id, month
