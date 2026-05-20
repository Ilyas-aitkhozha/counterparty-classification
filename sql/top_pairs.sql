SELECT
    sender_id_clean отправитель,
    receiver_id_clean получатель,
    COUNT(*)  число_операций,
    ROUND(SUM(amount_kzt), 2) оборот_кзт
FROM transactions
WHERE sender_valid  = 1
  AND receiver_valid = 1
  AND amount_kzt IS NOT NULL
GROUP BY sender_id_clean, receiver_id_clean
ORDER BY оборот_кзт DESC
LIMIT 10;