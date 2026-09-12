-- ============================================================
-- Retail Mart Analytics
-- BigQuery Data Warehouse Schema
-- ============================================================

-- Project:
-- retailmart-analytics-508414
--
-- Dataset:
-- retailmart_dw
--
-- Architecture:
--   Dimensions:
--     dim_date
--     dim_customer
--     dim_product
--
--   Facts:
--     fact_sales        - transaction grain
--     fact_sales_item   - line-item grain
--     fact_returns      - return-event grain
-- ============================================================

DROP TABLE IF EXISTS `retailmart-analytics-508414.retailmart_dw.fact_returns`;
DROP TABLE IF EXISTS `retailmart-analytics-508414.retailmart_dw.fact_sales_item`;
DROP TABLE IF EXISTS `retailmart-analytics-508414.retailmart_dw.fact_sales`;
DROP TABLE IF EXISTS `retailmart-analytics-508414.retailmart_dw.dim_product`;
DROP TABLE IF EXISTS `retailmart-analytics-508414.retailmart_dw.dim_customer`;
DROP TABLE IF EXISTS `retailmart-analytics-508414.retailmart_dw.dim_store`;
DROP TABLE IF EXISTS `retailmart-analytics-508414.retailmart_dw.dim_date`;

-- BigQuery dimensional model for RetailMart Analytics
-- Project: retailmart-analytics-508414
-- Dataset: retailmart_dw

CREATE SCHEMA IF NOT EXISTS `retailmart-analytics-508414.retailmart_dw`
OPTIONS(location='US');


-- ============================================================
-- DATE DIMENSION
-- ============================================================

CREATE TABLE IF NOT EXISTS `retailmart-analytics-508414.retailmart_dw.dim_date` (
  date_key INT64 NOT NULL,
  full_date DATE NOT NULL,
  year INT64,
  quarter INT64,
  month INT64,
  month_name STRING,
  week_of_year INT64,
  day_of_month INT64,
  day_of_week INT64,
  day_name STRING,
  is_weekend BOOL
);


-- ============================================================
-- STORE DIMENSION
-- ============================================================

CREATE TABLE IF NOT EXISTS `retailmart-analytics-508414.retailmart_dw.dim_store` (
  store_key INT64 NOT NULL,
  store_id INT64 NOT NULL,
  store_name STRING,
  city STRING,
  is_active BOOL
);


-- ============================================================
-- CUSTOMER DIMENSION
-- ============================================================

CREATE TABLE IF NOT EXISTS `retailmart-analytics-508414.retailmart_dw.dim_customer` (
  customer_key INT64 NOT NULL,
  customer_id INT64 NOT NULL,
  first_name STRING,
  last_name STRING,
  email STRING,
  phone STRING,
  city STRING,
  registration_date DATE,
  loyalty_tier STRING
)
CLUSTER BY loyalty_tier, city;


-- ============================================================
-- PRODUCT DIMENSION
-- ============================================================

CREATE TABLE IF NOT EXISTS `retailmart-analytics-508414.retailmart_dw.dim_product` (
  product_key INT64 NOT NULL,
  product_id INT64 NOT NULL,
  product_name STRING,
  category_id INT64,
  category_name STRING,
  unit_price NUMERIC,
  cost_price NUMERIC,
  is_active BOOL
)
CLUSTER BY category_id, product_id;


-- ============================================================
-- SALES FACT
-- Grain: one row per POS transaction
-- ============================================================

CREATE TABLE IF NOT EXISTS `retailmart-analytics-508414.retailmart_dw.fact_sales` (
  sales_key INT64 NOT NULL,
  transaction_id INT64 NOT NULL,
  date_key INT64 NOT NULL,
  store_key INT64 NOT NULL,
  customer_key INT64,
  transaction_date DATE NOT NULL,
  transaction_ts TIMESTAMP,
  payment_method STRING,
  gross_amount NUMERIC,
  discount_amount NUMERIC,
  tax_amount NUMERIC,
  net_amount NUMERIC,
  item_count INT64
)
PARTITION BY transaction_date
CLUSTER BY store_key, customer_key, payment_method;


-- ============================================================
-- SALES ITEM FACT
-- Grain: one row per transaction line item
-- ============================================================

CREATE TABLE IF NOT EXISTS `retailmart-analytics-508414.retailmart_dw.fact_sales_item` (
  sales_item_key INT64 NOT NULL,
  item_id INT64 NOT NULL,
  transaction_id INT64 NOT NULL,
  date_key INT64 NOT NULL,
  store_key INT64 NOT NULL,
  customer_key INT64,
  product_key INT64 NOT NULL,
  transaction_date DATE NOT NULL,
  quantity INT64,
  unit_price NUMERIC,
  line_total NUMERIC
)
PARTITION BY transaction_date
CLUSTER BY product_key, store_key;


-- ============================================================
-- RETURNS FACT
-- Grain: one row per return event
-- ============================================================

CREATE TABLE IF NOT EXISTS `retailmart-analytics-508414.retailmart_dw.fact_returns` (
  return_key INT64 NOT NULL,
  return_id INT64 NOT NULL,
  transaction_id INT64 NOT NULL,
  item_id INT64 NOT NULL,
  date_key INT64 NOT NULL,
  customer_key INT64,
  product_key INT64 NOT NULL,
  return_date DATE NOT NULL,
  return_quantity INT64,
  return_reason STRING,
  refund_amount NUMERIC,
  refund_status STRING
)
PARTITION BY return_date
CLUSTER BY product_key, refund_status;


-- ============================================================
-- DESIGN NOTES
-- ============================================================
--
-- fact_sales:
--   Transaction grain: one row per POS transaction.
--
-- fact_sales_item:
--   Line-item grain: one row per sold item line.
--
-- fact_returns:
--   Return-event grain: one row per return record.
--
-- Date partitioning:
--   Uses physical DATE columns rather than INT64 surrogate date keys.
--   This is supported directly by BigQuery partitioning.
--
-- Clustering:
--   Supports common filters and aggregations on store, product,
--   customer, payment method and refund status.
--
-- dim_product:
--   Category name is deliberately denormalized into the product
--   dimension to keep the warehouse star-shaped.