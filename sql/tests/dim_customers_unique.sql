-- A dimension must have exactly one row per key, or joins would double-count sales.
SELECT customer_id, COUNT(*) AS copies
FROM marts.dim_customers
GROUP BY customer_id
HAVING COUNT(*) > 1
