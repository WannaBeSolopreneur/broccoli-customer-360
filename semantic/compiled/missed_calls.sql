-- metric: missed_calls (Missed inbound calls)
SELECT tenant_id AS tenant_id,
       toStartOfMonth(started_at) AS month,
       count() AS value,
       count() AS rows_used
FROM marts.fct_calls
WHERE (direction = 'inbound')
  AND (channel = 'voice')
  AND (NOT is_spam)
  AND (answered_by != 'ai_agent')
GROUP BY tenant_id, month
ORDER BY tenant_id, month
