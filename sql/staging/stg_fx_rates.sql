-- rate_per_usd = how many units of the currency 1 US dollar buys.
-- To convert a local amount to USD: amount_local / rate_per_usd
CREATE OR REPLACE TABLE staging.stg_fx_rates AS
SELECT
    CAST(currency     AS VARCHAR) AS currency,
    CAST(rate_per_usd AS DOUBLE)  AS rate_per_usd,
    CAST(rate_date    AS DATE)    AS rate_date
FROM raw.fx_rates;
