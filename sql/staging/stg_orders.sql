CREATE OR REPLACE TABLE staging.stg_orders AS
SELECT
    CAST(order_id     AS VARCHAR)        AS order_id,
    CAST(line_number  AS INTEGER)        AS line_number,
    CAST(order_date   AS DATE)           AS order_date,
    CAST(customer_id  AS VARCHAR)        AS customer_id,
    CAST(product_id   AS VARCHAR)        AS product_id,
    CAST(quantity     AS INTEGER)        AS quantity,
    CAST(unit_price   AS DECIMAL(14, 2)) AS unit_price_local,
    CAST(discount_pct AS DECIMAL(5, 4))  AS discount_pct,
    CAST(currency     AS VARCHAR)        AS currency,
    CAST(channel      AS VARCHAR)        AS channel
FROM raw.orders;
