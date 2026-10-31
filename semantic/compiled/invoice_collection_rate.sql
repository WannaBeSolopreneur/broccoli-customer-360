-- metric: invoice_collection_rate (Invoice collection rate)
SELECT tenant_id AS tenant_id,
       toStartOfMonth(invoice_date) AS month,
       (sum(toFloat64(amount_paid))) / nullIf(sum(toFloat64(amount)), 0) AS value,
       sum(toFloat64(amount_paid)) AS numerator,
       sum(toFloat64(amount)) AS denominator,
       count() AS rows_used
FROM marts.fct_invoices
GROUP BY tenant_id, month
ORDER BY tenant_id, month
