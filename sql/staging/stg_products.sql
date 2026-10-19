CREATE OR REPLACE TABLE staging.stg_products AS
SELECT
    CAST(product_id     AS VARCHAR)       AS product_id,
    CAST(product_name   AS VARCHAR)       AS product_name,
    CAST(category       AS VARCHAR)       AS category,
    CAST(list_price_usd AS DECIMAL(12, 2)) AS list_price_usd,
    CAST(unit_cost_usd  AS DECIMAL(12, 2)) AS unit_cost_usd
FROM raw.products;
