-- Key columns and money columns must never be empty.
-- A NULL net_revenue_usd would mean a currency had no exchange rate.
SELECT *
FROM marts.fct_sales
WHERE order_id IS NULL
   OR order_date IS NULL
   OR customer_id IS NULL
   OR product_id IS NULL
   OR net_revenue_usd IS NULL
   OR cost_usd IS NULL
