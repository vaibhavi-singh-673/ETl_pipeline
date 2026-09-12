-- ============================================================
-- RETAIL MART ANALYTICS - BIGQUERY DATA WAREHOUSE
-- BILLING-FREE VERSION
-- ============================================================

-- ------------------------------------------------------------
-- 1. RESET WAREHOUSE DATASET
-- ------------------------------------------------------------

DROP SCHEMA IF EXISTS
`retailmart-analytics-508414.retailmart_dw`
CASCADE;

CREATE SCHEMA
`retailmart-analytics-508414.retailmart_dw`
OPTIONS (location = 'US');


-- ------------------------------------------------------------
-- 2. DIM_DATE
-- ------------------------------------------------------------

CREATE TABLE
`retailmart-analytics-508414.retailmart_dw.dim_date`
AS

SELECT
    CAST(FORMAT_DATE('%Y%m%d', d) AS INT64) AS date_key,
    d AS calendar_date,
    EXTRACT(DAYOFWEEK FROM d) AS day_of_week,
    FORMAT_DATE('%A', d) AS day_name,
    EXTRACT(DAY FROM d) AS day_of_month,
    EXTRACT(WEEK FROM d) AS week_of_year,
    EXTRACT(MONTH FROM d) AS month,
    FORMAT_DATE('%B', d) AS month_name,
    EXTRACT(QUARTER FROM d) AS quarter,
    EXTRACT(YEAR FROM d) AS year

FROM UNNEST(
    GENERATE_DATE_ARRAY(
        DATE '2023-01-01',
        DATE '2024-12-31'
    )
) AS d;


-- ------------------------------------------------------------
-- 3. DIM_STORE
-- ------------------------------------------------------------

CREATE TABLE
`retailmart-analytics-508414.retailmart_dw.dim_store`
AS

SELECT DISTINCT
    store_id

FROM
`retailmart-analytics-508414.retailmart_raw.sales_transactions`

WHERE store_id IS NOT NULL;


-- ------------------------------------------------------------
-- 4. DIM_CUSTOMER
-- ------------------------------------------------------------

CREATE TABLE
`retailmart-analytics-508414.retailmart_dw.dim_customer`
AS

SELECT
    customer_id,
    first_name,
    last_name,
    email,
    phone,
    city,
    registration_date,
    loyalty_tier

FROM
`retailmart-analytics-508414.retailmart_raw.customers`;


-- ------------------------------------------------------------
-- 5. DIM_PRODUCT
-- ------------------------------------------------------------

CREATE TABLE
`retailmart-analytics-508414.retailmart_dw.dim_product`
AS

SELECT
    p.product_id,
    p.product_name,
    p.category_id,
    c.category_name,
    p.unit_price

FROM
`retailmart-analytics-508414.retailmart_raw.products` p

LEFT JOIN
`retailmart-analytics-508414.retailmart_raw.categories` c

ON p.category_id = c.category_id;


-- ------------------------------------------------------------
-- 6. FACT_SALES
-- ------------------------------------------------------------

CREATE TABLE
`retailmart-analytics-508414.retailmart_dw.fact_sales`
AS

SELECT
    t.transaction_id,
    t.customer_id,
    t.store_id,
    t.transaction_date,
    t.transaction_time,
    t.payment_method,
    t.total_amount AS gross_amount,
    t.discount_amount,
    t.tax_amount,
    t.net_amount

FROM
`retailmart-analytics-508414.retailmart_raw.sales_transactions` t;


-- ------------------------------------------------------------
-- 7. FACT_SALES_ITEM
-- ------------------------------------------------------------

CREATE TABLE
`retailmart-analytics-508414.retailmart_dw.fact_sales_item`
AS

SELECT
    si.item_id,
    si.transaction_id,
    si.product_id,
    t.transaction_date,
    si.quantity,
    si.unit_price,
    si.line_total

FROM
`retailmart-analytics-508414.retailmart_raw.sales_items` si

INNER JOIN
`retailmart-analytics-508414.retailmart_raw.sales_transactions` t

ON si.transaction_id = t.transaction_id;


-- ------------------------------------------------------------
-- 8. FACT_RETURNS
-- ------------------------------------------------------------

CREATE TABLE
`retailmart-analytics-508414.retailmart_dw.fact_returns`
AS

SELECT
    return_id,
    transaction_id,
    item_id,
    customer_id,
    product_id,
    return_date,
    return_quantity,
    refund_amount,
    return_reason,
    refund_status

FROM
`retailmart-analytics-508414.retailmart_raw.returns`;


-- ------------------------------------------------------------
-- 9. VALIDATION
-- ------------------------------------------------------------

SELECT
    'dim_customer' AS table_name,
    COUNT(*) AS row_count
FROM
`retailmart-analytics-508414.retailmart_dw.dim_customer`

UNION ALL

SELECT
    'dim_date',
    COUNT(*)
FROM
`retailmart-analytics-508414.retailmart_dw.dim_date`

UNION ALL

SELECT
    'dim_product',
    COUNT(*)
FROM
`retailmart-analytics-508414.retailmart_dw.dim_product`

UNION ALL

SELECT
    'dim_store',
    COUNT(*)
FROM
`retailmart-analytics-508414.retailmart_dw.dim_store`

UNION ALL

SELECT
    'fact_returns',
    COUNT(*)
FROM
`retailmart-analytics-508414.retailmart_dw.fact_returns`

UNION ALL

SELECT
    'fact_sales',
    COUNT(*)
FROM
`retailmart-analytics-508414.retailmart_dw.fact_sales`

UNION ALL

SELECT
    'fact_sales_item',
    COUNT(*)
FROM
`retailmart-analytics-508414.retailmart_dw.fact_sales_item`

ORDER BY table_name;