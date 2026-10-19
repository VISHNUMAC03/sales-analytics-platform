SELECT product_id, COUNT(*) AS copies
FROM marts.dim_products
GROUP BY product_id
HAVING COUNT(*) > 1
