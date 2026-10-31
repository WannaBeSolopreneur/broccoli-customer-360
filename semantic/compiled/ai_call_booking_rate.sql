-- metric: ai_call_booking_rate (AI call booking rate)
SELECT tenant_id AS tenant_id,
       toStartOfMonth(started_at) AS month,
       (countIf(booked)) / nullIf(count(), 0) AS value,
       countIf(booked) AS numerator,
       count() AS denominator,
       count() AS rows_used
FROM marts.fct_calls
WHERE (direction = 'inbound')
  AND (answered_by = 'ai_agent')
  AND (NOT is_spam)
GROUP BY tenant_id, month
ORDER BY tenant_id, month
