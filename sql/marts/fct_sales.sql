-- FACT: one row per order line (this is the table's "grain").
-- Facts hold the measurable numbers (quantity, revenue, cost) plus keys that
-- point to the dimensions (customer_id -> dim_customers, product_id -> dim_products,
-- order_date -> dim_date). Together they form a "star schema".
--
-- LEFT JOINs are deliberate: if a currency or product were missing, the row
-- stays and its USD amount becomes NULL, which the quality checks then catch.
-- An INNER JOIN would silently drop those sales and under-report revenue.
CREATE OR REPLACE TABLE marts.fct_sales AS
WITH priced AS (
    SELECT
        o.order_id,
        o.line_number,
        o.order_id || '-' || CAST(o.line_number AS VARCHAR) AS sales_line_id,
        o.order_date,
        CAST(strftime(o.order_date, '%Y%m%d') AS INTEGER) AS date_key,
        o.customer_id,
        o.product_id,
        o.channel,
        o.currency,
        o.quantity,
        o.unit_price_local,
        o.discount_pct,
        fx.rate_per_usd,
        o.quantity * o.unit_price_local / fx.rate_per_usd                       AS gross_usd,
        o.quantity * o.unit_price_local * o.discount_pct / fx.rate_per_usd      AS discount_usd,
        o.quantity * o.unit_price_local * (1 - o.discount_pct) / fx.rate_per_usd AS net_usd,
        o.quantity * p.unit_cost_usd                                            AS cost_usd
    FROM staging.stg_orders AS o
    LEFT JOIN staging.stg_fx_rates AS fx ON o.currency = fx.currency
    LEFT JOIN staging.stg_products AS p ON o.product_id = p.product_id
)
SELECT
    sales_line_id,
    order_id,
    line_number,
    order_date,
    date_key,
    customer_id,
    product_id,
    channel,
    currency,
    quantity,
    unit_price_local,
    discount_pct,
    rate_per_usd,
    ROUND(gross_usd, 2)            AS gross_revenue_usd,
    ROUND(discount_usd, 2)         AS discount_usd,
    ROUND(net_usd, 2)              AS net_revenue_usd,
    ROUND(cost_usd, 2)             AS cost_usd,
    ROUND(net_usd - cost_usd, 2)   AS profit_usd
FROM priced;
