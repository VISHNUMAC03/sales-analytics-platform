-- Referential integrity: every sale must belong to a known customer.
SELECT f.sales_line_id, f.customer_id
FROM marts.fct_sales AS f
LEFT JOIN marts.dim_customers AS c ON f.customer_id = c.customer_id
WHERE c.customer_id IS NULL
