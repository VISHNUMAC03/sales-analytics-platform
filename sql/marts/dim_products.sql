-- DIMENSION: describes WHAT was bought. One row per product.
CREATE OR REPLACE TABLE marts.dim_products AS
SELECT
    product_id,
    product_name,
    category,
    list_price_usd,
    unit_cost_usd,
    ROUND((list_price_usd - unit_cost_usd) / list_price_usd, 4) AS list_margin_pct,
    CASE
        WHEN list_price_usd >= 150 THEN 'Premium'
        WHEN list_price_usd >= 50  THEN 'Mid-range'
        ELSE 'Budget'
    END AS price_band
FROM staging.stg_products;
