-- REPORTING: monthly KPIs, with month-over-month growth using a window function (LAG).
CREATE OR REPLACE TABLE reporting.rpt_monthly_revenue AS
WITH monthly AS (
    SELECT
        CAST(date_trunc('month', order_date) AS DATE) AS month_start,
        SUM(net_revenue_usd)            AS revenue_usd,
        SUM(profit_usd)                 AS profit_usd,
        COUNT(DISTINCT order_id)        AS orders,
        COUNT(DISTINCT customer_id)     AS active_customers
    FROM reporting.sales_enriched
    GROUP BY 1
)
SELECT
    month_start,
    ROUND(revenue_usd, 2)                        AS revenue_usd,
    ROUND(profit_usd, 2)                         AS profit_usd,
    orders,
    active_customers,
    ROUND(revenue_usd / orders, 2)               AS avg_order_value_usd,
    ROUND(100 * (revenue_usd / LAG(revenue_usd) OVER (ORDER BY month_start) - 1), 1)
                                                 AS revenue_growth_pct
FROM monthly
ORDER BY month_start;
