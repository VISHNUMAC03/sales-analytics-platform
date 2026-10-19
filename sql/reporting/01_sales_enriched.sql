-- REPORTING: the star schema joined back into one wide, easy-to-query table.
-- BI tools and dashboards love this: every filter column is right there.
CREATE OR REPLACE TABLE reporting.sales_enriched AS
SELECT
    f.sales_line_id,
    f.order_id,
    f.order_date,
    d.year,
    d.quarter,
    d.year_month,
    d.day_name,
    f.customer_id,
    c.customer_name,
    c.country,
    c.region,
    c.segment,
    f.product_id,
    p.product_name,
    p.category,
    p.price_band,
    f.channel,
    f.currency,
    f.quantity,
    f.gross_revenue_usd,
    f.discount_usd,
    f.net_revenue_usd,
    f.cost_usd,
    f.profit_usd
FROM marts.fct_sales AS f
LEFT JOIN marts.dim_customers AS c ON f.customer_id = c.customer_id
LEFT JOIN marts.dim_products  AS p ON f.product_id  = p.product_id
LEFT JOIN marts.dim_date      AS d ON f.date_key    = d.date_key;
