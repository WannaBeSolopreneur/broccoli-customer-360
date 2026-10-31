-- metric: lead_to_booking_rate (Lead to booking rate)
SELECT tenant_id AS tenant_id,
       toStartOfMonth(received_at) AS month,
       (countIf(booked_within_14d)) / nullIf(count(), 0) AS value,
       countIf(booked_within_14d) AS numerator,
       count() AS denominator,
       count() AS rows_used
FROM marts.fct_leads
GROUP BY tenant_id, month
ORDER BY tenant_id, month
