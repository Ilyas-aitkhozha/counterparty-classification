WITH incoming AS (
    SELECT receiver_id_clean rec, sender_id_clean sen, SUM(amount_kzt) sum
    FROM transactions
    WHERE sender_valid   = 1
      AND receiver_valid = 1
      AND amount_kzt > 0
    GROUP BY receiver_id_clean, sender_id_clean
),
totals AS (
    SELECT rec, SUM(sum) sum_total
    FROM incoming
    GROUP BY rec
),
shares AS (
    SELECT i.rec, i.sen, ROUND(i.sum, 2) sum,
        ROUND(t.sum_total, 2) sum_total, ROUND(i.sum / t.sum_total, 4) shar,
        RANK() OVER (PARTITION BY i.rec ORDER BY i.sum DESC) rnk
    FROM incoming i
    JOIN totals t ON t.rec = i.rec
    WHERE i.sum / t.sum_total > 0.70
)
SELECT
    rec получатель,
    sen  главный_источник,
    sum сумма_от_источника,
    sum_total  сумма_входящих,
    ROUND(shar * 100, 1) || '%'  доля
FROM shares
WHERE rnk = 1
ORDER BY shar DESC;