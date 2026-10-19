-- Referential integrity: every sale must be for a known product.
SELECT f.sales_line_id, f.product_id
FROM marts.fct_sales AS f
LEFT JOIN marts.dim_products AS p ON f.product_id = p.product_id
WHERE p.product_id IS NULL
