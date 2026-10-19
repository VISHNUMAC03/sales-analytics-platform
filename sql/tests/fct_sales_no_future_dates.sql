-- Orders cannot be placed in the future.
SELECT sales_line_id, order_date
FROM marts.fct_sales
WHERE order_date > current_date
