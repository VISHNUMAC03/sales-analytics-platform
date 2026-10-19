-- Each order line must appear exactly once. Returns the duplicated lines.
SELECT order_id, line_number, COUNT(*) AS copies
FROM marts.fct_sales
GROUP BY order_id, line_number
HAVING COUNT(*) > 1
