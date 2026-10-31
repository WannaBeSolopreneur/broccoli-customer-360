SELECT 'speed_to_lead_median_sec' AS metric, count() AS n_tenants,
       avg(value) AS average,
       if(count() >= 5, quantileExact(0.25)(value), NULL) AS p25,
       if(count() >= 5, quantileExact(0.5)(value), NULL) AS median,
       if(count() >= 5, quantileExact(0.75)(value), NULL) AS p75
FROM (-- metric: speed_to_lead_median_sec (Speed to lead (median seconds))
SELECT tenant_id AS tenant_id,
       quantileExact(0.5)(speed_to_lead_sec) AS value,
       count() AS rows_used
FROM marts.fct_leads
WHERE (first_contact_at IS NOT NULL)
GROUP BY tenant_id
ORDER BY tenant_id) HAVING n_tenants >= 3
UNION ALL
SELECT 'lead_to_booking_rate' AS metric, count() AS n_tenants,
       avg(value) AS average,
       if(count() >= 5, quantileExact(0.25)(value), NULL) AS p25,
       if(count() >= 5, quantileExact(0.5)(value), NULL) AS median,
       if(count() >= 5, quantileExact(0.75)(value), NULL) AS p75
FROM (-- metric: lead_to_booking_rate (Lead to booking rate)
SELECT tenant_id AS tenant_id,
       (countIf(booked_within_14d)) / nullIf(count(), 0) AS value,
       countIf(booked_within_14d) AS numerator,
       count() AS denominator,
       count() AS rows_used
FROM marts.fct_leads
GROUP BY tenant_id
ORDER BY tenant_id) HAVING n_tenants >= 3
UNION ALL
SELECT 'call_answer_rate' AS metric, count() AS n_tenants,
       avg(value) AS average,
       if(count() >= 5, quantileExact(0.25)(value), NULL) AS p25,
       if(count() >= 5, quantileExact(0.5)(value), NULL) AS median,
       if(count() >= 5, quantileExact(0.75)(value), NULL) AS p75
FROM (-- metric: call_answer_rate (Call answer rate)
SELECT tenant_id AS tenant_id,
       (countIf(answered_by = 'ai_agent')) / nullIf(count(), 0) AS value,
       countIf(answered_by = 'ai_agent') AS numerator,
       count() AS denominator,
       count() AS rows_used
FROM marts.fct_calls
WHERE (direction = 'inbound')
  AND (channel = 'voice')
  AND (NOT is_spam)
GROUP BY tenant_id
ORDER BY tenant_id) HAVING n_tenants >= 3
UNION ALL
SELECT 'ai_call_booking_rate' AS metric, count() AS n_tenants,
       avg(value) AS average,
       if(count() >= 5, quantileExact(0.25)(value), NULL) AS p25,
       if(count() >= 5, quantileExact(0.5)(value), NULL) AS median,
       if(count() >= 5, quantileExact(0.75)(value), NULL) AS p75
FROM (-- metric: ai_call_booking_rate (AI call booking rate)
SELECT tenant_id AS tenant_id,
       (countIf(booked)) / nullIf(count(), 0) AS value,
       countIf(booked) AS numerator,
       count() AS denominator,
       count() AS rows_used
FROM marts.fct_calls
WHERE (direction = 'inbound')
  AND (answered_by = 'ai_agent')
  AND (NOT is_spam)
GROUP BY tenant_id
ORDER BY tenant_id) HAVING n_tenants >= 3
UNION ALL
SELECT 'revenue_per_customer' AS metric, count() AS n_tenants,
       avg(value) AS average,
       if(count() >= 5, quantileExact(0.25)(value), NULL) AS p25,
       if(count() >= 5, quantileExact(0.5)(value), NULL) AS median,
       if(count() >= 5, quantileExact(0.75)(value), NULL) AS p75
FROM (-- metric: revenue_per_customer (Revenue per active customer)
SELECT tenant_id AS tenant_id,
       (sum(toFloat64(total_revenue))) / nullIf(uniqExact(customer_key), 0) AS value,
       sum(toFloat64(total_revenue)) AS numerator,
       uniqExact(customer_key) AS denominator,
       count() AS rows_used
FROM marts.fct_jobs
WHERE (status = 'Completed')
GROUP BY tenant_id
ORDER BY tenant_id) HAVING n_tenants >= 3
UNION ALL
SELECT 'membership_renewal_rate' AS metric, count() AS n_tenants,
       avg(value) AS average,
       if(count() >= 5, quantileExact(0.25)(value), NULL) AS p25,
       if(count() >= 5, quantileExact(0.5)(value), NULL) AS median,
       if(count() >= 5, quantileExact(0.75)(value), NULL) AS p75
FROM (-- metric: membership_renewal_rate (Membership renewal rate)
SELECT tenant_id AS tenant_id,
       (countIf(renewed)) / nullIf(count(), 0) AS value,
       countIf(renewed) AS numerator,
       count() AS denominator,
       count() AS rows_used
FROM marts.fct_memberships
WHERE (renewal_due)
GROUP BY tenant_id
ORDER BY tenant_id) HAVING n_tenants >= 3
