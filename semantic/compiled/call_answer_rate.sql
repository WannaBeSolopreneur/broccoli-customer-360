-- metric: call_answer_rate (Call answer rate)
SELECT tenant_id AS tenant_id,
       toStartOfMonth(started_at) AS month,
       (countIf(answered_by = 'ai_agent')) / nullIf(count(), 0) AS value,
       countIf(answered_by = 'ai_agent') AS numerator,
       count() AS denominator,
       count() AS rows_used
FROM marts.fct_calls
WHERE (direction = 'inbound')
  AND (channel = 'voice')
  AND (NOT is_spam)
GROUP BY tenant_id, month
ORDER BY tenant_id, month
