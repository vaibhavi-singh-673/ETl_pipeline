-- ============================================================
-- RETAIL MART ANALYTICS
-- BIGQUERY BUSINESS ANALYTICS PROCEDURES
-- ============================================================

-- ============================================================
-- 1. SALES METRICS
-- ============================================================

CREATE OR REPLACE PROCEDURE
`retailmart-analytics-508414.retailmart_dw.sp_sales_metrics`(
    p_start_date DATE,
    p_end_date DATE
)
BEGIN

  -- Revenue = net_amount
  -- Net amount already represents the final transaction amount
  -- after discount and including tax.

  WITH monthly AS (

    SELECT
      DATE_TRUNC(transaction_date, MONTH) AS month,

      SUM(net_amount) AS total_revenue,

      SUM(gross_amount) AS gross_sales,

      SUM(discount_amount) AS discounts,

      SUM(tax_amount) AS tax_amount,

      COUNT(*) AS transaction_count

    FROM
      `retailmart-analytics-508414.retailmart_dw.fact_sales`

    WHERE transaction_date BETWEEN p_start_date AND p_end_date

    GROUP BY month
  ),

  metrics AS (

    SELECT
      month,
      total_revenue,
      gross_sales,
      discounts,
      tax_amount,
      transaction_count,

      LAG(total_revenue)
        OVER (ORDER BY month) AS previous_month_revenue,

      LAG(total_revenue, 12)
        OVER (ORDER BY month) AS prior_year_revenue

    FROM monthly
  )

  SELECT
    month,
    total_revenue,
    gross_sales,
    discounts,
    tax_amount,
    transaction_count,

    previous_month_revenue,

    SAFE_DIVIDE(
      total_revenue - previous_month_revenue,
      previous_month_revenue
    ) * 100 AS mom_revenue_pct,

    prior_year_revenue,

    SAFE_DIVIDE(
      total_revenue - prior_year_revenue,
      prior_year_revenue
    ) * 100 AS yoy_revenue_pct

  FROM metrics

  ORDER BY month;

END;


-- ============================================================
-- 2. RETURNS ANALYSIS
-- ============================================================

CREATE OR REPLACE PROCEDURE
`retailmart-analytics-508414.retailmart_dw.sp_returns_analysis`(
    p_start_date DATE,
    p_end_date DATE
)
BEGIN

  -- Sold quantity is calculated from fact_sales_item.
  -- Returned quantity is calculated from fact_returns.
  -- Return rate = returned quantity / sold quantity.
  -- Revenue impact = processed refund amount.

  WITH sold AS (

    SELECT
      si.product_id,

      SUM(si.quantity) AS sold_qty,

      SUM(si.line_total) AS gross_sales

    FROM
      `retailmart-analytics-508414.retailmart_dw.fact_sales_item` si

    WHERE si.transaction_date BETWEEN p_start_date AND p_end_date

    GROUP BY si.product_id
  ),

  returned AS (

    SELECT
      r.product_id,

      SUM(r.return_quantity) AS returned_qty,

      SUM(
        CASE
          WHEN LOWER(r.refund_status) = 'processed'
          THEN r.refund_amount
          ELSE 0
        END
      ) AS refund_amount

    FROM
      `retailmart-analytics-508414.retailmart_dw.fact_returns` r

    WHERE r.return_date BETWEEN p_start_date AND p_end_date

    GROUP BY r.product_id
  )

  SELECT

    p.category_id,

    p.category_name,

    SUM(COALESCE(s.sold_qty, 0)) AS sold_quantity,

    SUM(COALESCE(r.returned_qty, 0)) AS returned_quantity,

    SAFE_DIVIDE(
      SUM(COALESCE(r.returned_qty, 0)),
      SUM(COALESCE(s.sold_qty, 0))
    ) * 100 AS return_rate_pct,

    SUM(COALESCE(r.refund_amount, 0)) AS revenue_impact

  FROM
    `retailmart-analytics-508414.retailmart_dw.dim_product` p

  LEFT JOIN sold s
    ON s.product_id = p.product_id

  LEFT JOIN returned r
    ON r.product_id = p.product_id

  GROUP BY
    p.category_id,
    p.category_name

  ORDER BY
    revenue_impact DESC;

END;