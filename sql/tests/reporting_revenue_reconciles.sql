-- Reconciliation: the reporting tables must add up to the fact table.
-- If a join fanned out or dropped rows, the totals would differ.
WITH totals AS (
    SELECT
        (SELECT SUM(net_revenue_usd) FROM marts.fct_sales)                    AS fact_total,
        (SELECT SUM(net_revenue_usd) FROM reporting.sales_enriched)           AS enriched_total,
        (SELECT SUM(revenue_usd)     FROM reporting.rpt_monthly_revenue)      AS monthly_total,
        (SELECT SUM(revenue_usd)     FROM reporting.rpt_customer_performance) AS customer_total
)
SELECT *
FROM totals
WHERE ABS(fact_total - enriched_total) > 0.01
   OR ABS(fact_total - monthly_total)  > 1
   OR ABS(fact_total - customer_total) > 1
