-- =====================================================================
-- 06_mart_scorecard.sql  |  Channel scorecard and the profit waterfall.
-- "What the platform says" vs "what the cash sees", same window, same rows.
-- =====================================================================

CREATE OR REPLACE TABLE mart_channel_scorecard AS
SELECT
    channel,
    SUM(spend)                                    AS spend,
    SUM(credit)                                   AS credit,
    SUM(spend) - SUM(credit)                      AS net_cost,
    SUM(attributed)                               AS attributed,
    SUM(attributed) / SUM(spend)                  AS platform_roas,
    SUM(spend) / SUM(attributed)                  AS acos,
    SUM(spend) / SUM(gmv_on_ad_days)              AS tacos,
    ANY_VALUE(k)                                  AS k,
    SUM(incremental_gmv)                          AS incremental_gmv,
    SUM(incremental_gmv) / SUM(spend)             AS iroas_applied,
    SUM(incremental_contribution)                 AS incremental_contribution,
    SUM(incremental_gmv) / SUM(incremental_contribution) AS breakeven_iroas,
    SUM(incremental_profit)                       AS incremental_profit,
    SUM(incremental_gmv * share_cogs)             AS inc_cost_cogs,
    SUM(incremental_gmv * share_fees_tax_returns) AS inc_cost_fees_tax_returns,
    SUM(incremental_gmv * share_logistics_affiliates) AS inc_cost_logistics_affiliates
FROM mart_sku_channel_economics
GROUP BY channel;

-- Waterfall in long format (step order, label, signed value, kind)
CREATE OR REPLACE TABLE mart_profit_waterfall AS
SELECT channel, step, label, value, kind FROM (
    SELECT channel, 1 AS step, 'GMV atribuído pela plataforma' AS label, attributed AS value, 'total' AS kind FROM mart_channel_scorecard
    UNION ALL SELECT channel, 2, 'Venda que viria de qualquer jeito', -(attributed - incremental_gmv), 'delta' FROM mart_channel_scorecard
    UNION ALL SELECT channel, 3, 'GMV incremental', incremental_gmv, 'subtotal' FROM mart_channel_scorecard
    UNION ALL SELECT channel, 4, 'CMV', -inc_cost_cogs, 'delta' FROM mart_channel_scorecard
    UNION ALL SELECT channel, 5, 'Taxas, impostos e devoluções', -inc_cost_fees_tax_returns, 'delta' FROM mart_channel_scorecard
    UNION ALL SELECT channel, 6, 'Frete, embalagem e afiliados', -inc_cost_logistics_affiliates, 'delta' FROM mart_channel_scorecard
    UNION ALL SELECT channel, 7, 'Contribuição incremental', incremental_contribution, 'subtotal' FROM mart_channel_scorecard
    UNION ALL SELECT channel, 8, 'Investimento em ads', -spend, 'delta' FROM mart_channel_scorecard
    UNION ALL SELECT channel, 9, 'Créditos de ROI protection', credit, 'delta' FROM mart_channel_scorecard
    UNION ALL SELECT channel, 10, 'Lucro incremental', incremental_profit, 'total' FROM mart_channel_scorecard
)
ORDER BY channel, step;

-- TikTok ROI protection summary
CREATE OR REPLACE TABLE mart_roi_protection AS
SELECT
    protection_status,
    COUNT(*)                     AS campaign_days,
    SUM(credit_recomputed)       AS credit_recomputed,
    SUM(credit_statement)        AS credit_statement,
    SUM(cost)                    AS cost
FROM fct_tiktok_campaign_day
GROUP BY protection_status;
