-- metric: revenue_per_customer (Revenue per active customer)
SELECT tenant_id AS tenant_id,
       toStartOfMonth(created_on) AS month,
       (sum(toFloat64(total_revenue))) / nullIf(uniqExact(customer_key), 0) AS value,
       sum(toFloat64(total_revenue)) AS numerator,
       uniqExact(customer_key) AS denominator,
       count() AS rows_used
FROM marts.fct_jobs
WHERE (status = 'Completed')
GROUP BY tenant_id, month
ORDER BY tenant_id, month
