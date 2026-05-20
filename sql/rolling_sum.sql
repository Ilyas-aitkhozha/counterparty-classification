WITH monthly AS (
    SELECT
        sender_id_clean sen,
        STRFTIME('%Y-%m', date_clean) mon,
        SUM(amount_kzt) sum
    FROM transactions
    WHERE sender_valid = 1
      AND date_clean IS NOT NULL
      AND amount_kzt IS NOT NULL
    GROUP BY sender_id_clean, mon
)
SELECT
    sen отправитель,
    mon месяц,
    ROUND(sum, 2) сумма_за_месяц,
    ROUND(SUM(sum) OVER (
        PARTITION BY sen
        ORDER BY mon
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ), 2)  нарастающий_итог
FROM monthly
ORDER BY sen, mon;