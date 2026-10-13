-- =====================================================================
-- 03_core.sql  |  The one fact everything else reads.
-- Grain: day x channel x SKU. OMS is the spine (it always has a row);
-- ad metrics hang off it and are NULL when the export did not exist.
-- =====================================================================

CREATE OR REPLACE TABLE dim_sku AS
SELECT sku_id, sku_name, category, list_price::DOUBLE AS list_price, unit_cogs::DOUBLE AS unit_cogs
FROM raw_sku_catalog;

CREATE OR REPLACE TABLE dim_channel AS
SELECT * FROM raw_channel_cost_assumptions;

-- TikTok GMV Max campaign-day, with ROI protection RECOMPUTED from the rules
-- (TikTok help center, updated Jun/2026):
--   eligible  : ROI < 90% of daily target AND more than 20 orders AND no manual Target ROI edit that day
--   credit    : total cost - total gross revenue / (daily ROI target x 0.9)
-- The platform statement is joined only for audit; nothing here trusts it.
CREATE OR REPLACE TABLE fct_tiktok_campaign_day AS
WITH agg AS (
    SELECT ad_date, campaign_id,
           SUM(spend)              AS cost,
           SUM(attributed_revenue) AS gross_revenue,
           SUM(attributed_orders)  AS orders
    FROM stg_ads_tiktok
    GROUP BY ALL
)
SELECT
    a.ad_date,
    a.campaign_id,
    a.cost,
    a.gross_revenue,
    a.orders,
    a.gross_revenue / NULLIF(a.cost, 0)                         AS roi,
    s.target_roi,
    s.manual_target_roi_edits,
    CASE
        WHEN a.gross_revenue / NULLIF(a.cost, 0) >= 0.9 * s.target_roi THEN 'roi_acima_de_90pct'
        WHEN a.orders <= 20                                            THEN 'ate_20_pedidos'
        WHEN s.manual_target_roi_edits > 0                             THEN 'meta_editada_no_dia'
        ELSE 'elegivel'
    END                                                         AS protection_status,
    CASE
        WHEN a.gross_revenue / NULLIF(a.cost, 0) < 0.9 * s.target_roi
         AND a.orders > 20 AND s.manual_target_roi_edits = 0
        THEN ROUND(a.cost - a.gross_revenue / (s.target_roi * 0.9), 2)
        ELSE 0
    END                                                         AS credit_recomputed,
    COALESCE(c.credit_amount, 0)                                AS credit_statement
FROM agg a
JOIN raw_tiktok_campaign_settings_daily s
  ON s.campaign_id = a.campaign_id AND CAST(s.stat_date AS DATE) = a.ad_date
LEFT JOIN raw_tiktok_roi_protection_credits c
  ON c.campaign_id = a.campaign_id AND CAST(c.stat_date AS DATE) = a.ad_date;

-- Statement credits allocated to SKU-days in proportion to cost share
CREATE OR REPLACE TABLE int_credit_by_sku_day AS
SELECT t.ad_date, t.channel, t.sku_id,
       f.credit_statement * t.spend / NULLIF(f.cost, 0) AS credit
FROM stg_ads_tiktok t
JOIN fct_tiktok_campaign_day f USING (ad_date, campaign_id)
WHERE f.credit_statement > 0;

-- The fact ------------------------------------------------------------
CREATE OR REPLACE TABLE fct_sku_channel_day AS
SELECT
    o.d,
    o.channel,
    o.sku_id,
    k.category,
    e.arm,
    CASE WHEN o.d >= e.test_start THEN 'test' ELSE 'pre' END       AS period,
    o.orders,
    o.units,
    o.gross_revenue,
    o.refunded_revenue,
    o.affiliate_commission,
    (cov.ad_date IS NOT NULL)                                       AS ad_measured,
    -- measured day without a row for this SKU = ads were off = a real zero
    CASE WHEN cov.ad_date IS NULL THEN NULL ELSE COALESCE(a.spend, 0) END              AS ad_spend,
    CASE WHEN cov.ad_date IS NULL THEN NULL ELSE COALESCE(a.attributed_revenue, 0) END AS attributed_revenue,
    CASE WHEN cov.ad_date IS NULL THEN NULL ELSE COALESCE(a.attributed_orders, 0) END  AS attributed_orders,
    COALESCE(cr.credit, 0)                                          AS credit,
    -- cost components of the order itself (before ads)
    o.units * k.unit_cogs                                           AS cost_cogs,
    o.refunded_revenue
      + (o.gross_revenue - o.refunded_revenue) * (c.marketplace_fee_pct + c.tax_pct)
      + o.orders * c.fixed_fee_per_order                            AS cost_fees_tax_returns,
    o.orders * (c.seller_shipping_per_order + c.packaging_per_order)
      + o.affiliate_commission                                      AS cost_logistics_affiliates
FROM stg_oms o
JOIN dim_sku k                    USING (sku_id)
JOIN dim_channel c                USING (channel)
JOIN raw_experiment_assignment e  USING (channel, sku_id)
LEFT JOIN stg_ad_report_coverage cov ON cov.channel = o.channel AND cov.ad_date = o.d
LEFT JOIN stg_ads a               ON a.channel = o.channel AND a.sku_id = o.sku_id AND a.ad_date = o.d
LEFT JOIN int_credit_by_sku_day cr ON cr.channel = o.channel AND cr.sku_id = o.sku_id AND cr.ad_date = o.d;

-- Contribution before ads: the ONLY place it is defined.
CREATE OR REPLACE VIEW v_fct_contribution AS
SELECT *,
       gross_revenue - cost_cogs - cost_fees_tax_returns - cost_logistics_affiliates AS contribution_before_ads
FROM fct_sku_channel_day;
