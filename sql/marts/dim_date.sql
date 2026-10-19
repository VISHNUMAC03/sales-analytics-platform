-- DIMENSION: describes WHEN. One row per calendar day between the first and last order.
-- A date table makes "sales by month / quarter / weekday" trivial and includes days with no sales.
CREATE OR REPLACE TABLE marts.dim_date AS
WITH days AS (
    SELECT UNNEST(generate_series(
        CAST(MIN(order_date) AS TIMESTAMP),
        CAST(MAX(order_date) AS TIMESTAMP),
        INTERVAL 1 DAY
    )) AS day_ts
    FROM staging.stg_orders
)
SELECT
    CAST(day_ts AS DATE)                         AS date_day,
    CAST(strftime(day_ts, '%Y%m%d') AS INTEGER)  AS date_key,
    year(day_ts)                                 AS year,
    quarter(day_ts)                              AS quarter,
    month(day_ts)                                AS month,
    strftime(day_ts, '%B')                       AS month_name,
    strftime(day_ts, '%Y-%m')                    AS year_month,
    dayname(day_ts)                              AS day_name,
    isodow(day_ts) IN (6, 7)                     AS is_weekend
FROM days;
