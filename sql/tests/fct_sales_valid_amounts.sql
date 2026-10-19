-- Business rules: positive quantities, non-negative revenue, sensible discounts,
-- net revenue never larger than gross revenue.
SELECT *
FROM marts.fct_sales
WHERE quantity <= 0
   OR net_revenue_usd < 0
   OR discount_pct < 0 OR discount_pct >= 1
   OR net_revenue_usd > gross_revenue_usd
