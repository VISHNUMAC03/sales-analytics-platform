-- REPORTING: lifetime value per customer, ranked into tiers with NTILE.
-- NTILE(4) splits customers into 4 equal-sized groups by revenue.
CREATE OR REPLACE TABLE reporting.rpt_customer_performance AS
WITH per_customer AS (
    SELECT
        customer_id,
        customer_name,
        country,
        region,
        segment,
        COUNT(DISTINCT order_id)   AS orders,
        SUM(quantity)              AS units,
        SUM(net_revenue_usd)       AS revenue_usd,
        SUM(profit_usd)            AS profit_usd,
        MIN(order_date)            AS first_order_date,
        MAX(order_date)            AS last_order_date
    FROM reporting.sales_enriched
    GROUP BY ALL
)
SELECT
    *,
    ROUND(revenue_usd / orders, 2) AS avg_order_value_usd,
    RANK() OVER (ORDER BY revenue_usd DESC) AS revenue_rank,
    CASE NTILE(4) OVER (ORDER BY revenue_usd DESC)
        WHEN 1 THEN 'Platinum'
        WHEN 2 THEN 'Gold'
        WHEN 3 THEN 'Silver'
        ELSE 'Bronze'
    END AS customer_tier
FROM per_customer;
