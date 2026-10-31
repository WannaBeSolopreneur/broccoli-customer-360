-- metric: membership_renewal_rate (Membership renewal rate)
SELECT tenant_id AS tenant_id,
       toStartOfMonth(period_end) AS month,
       (countIf(renewed)) / nullIf(count(), 0) AS value,
       countIf(renewed) AS numerator,
       count() AS denominator,
       count() AS rows_used
FROM marts.fct_memberships
WHERE (renewal_due)
GROUP BY tenant_id, month
ORDER BY tenant_id, month
