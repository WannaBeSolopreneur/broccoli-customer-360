-- metric: active_customers (Active customers)
SELECT tenant_id AS tenant_id,
       toStartOfMonth(created_on) AS month,
       uniqExact(customer_key) AS value,
       count() AS rows_used
FROM marts.fct_jobs
WHERE (status = 'Completed')
GROUP BY tenant_id, month
ORDER BY tenant_id, month
