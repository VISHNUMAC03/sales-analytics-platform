-- DIMENSION: describes WHO bought. One row per customer.
-- Dimensions hold the descriptive attributes you filter and group by.
CREATE OR REPLACE TABLE marts.dim_customers AS
SELECT
    customer_id,
    customer_name,
    email,
    country,
    region,
    segment,
    signup_date
FROM staging.stg_customers;
