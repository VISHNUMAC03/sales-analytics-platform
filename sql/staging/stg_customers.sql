-- STAGING: one clean, correctly-typed copy of each raw table.
-- Rule of thumb: staging only renames and casts. No joins, no business logic.
CREATE OR REPLACE TABLE staging.stg_customers AS
SELECT
    CAST(customer_id   AS VARCHAR) AS customer_id,
    CAST(customer_name AS VARCHAR) AS customer_name,
    CAST(email         AS VARCHAR) AS email,
    CAST(country       AS VARCHAR) AS country,
    CAST(region        AS VARCHAR) AS region,
    CAST(segment       AS VARCHAR) AS segment,
    CAST(signup_date   AS DATE)    AS signup_date
FROM raw.customers;
