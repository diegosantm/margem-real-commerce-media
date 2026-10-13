-- =====================================================================
-- 05_mart_unit_economics.sql  |  Break-even ROAS per SKU x channel.
--
-- An extra R$1 of platform-attributed GMV is worth only k x cm in profit:
--   k  = share of attributed GMV that is incremental (from the experiment)
--   cm = contribution margin before ads (OMS, after COGS, fees, tax,
--        returns, shipping, packaging and affiliate commission)
-- So the ads break even when   platform_ROAS x k x cm = 1
--          breakeven_platform_roas = 1 / (k x cm)
-- That is the minimum target to type into GMV Max / Custom ROAS, or the
-- maximum ACOS (= k x cm) for teams that think in ACOS.
-- =====================================================================

CREATE OR REPLACE TABLE mart_sku_channel_economics AS
WITH econ AS (
    SELECT
        channel, sku_id, category,
        SUM(gross_revenue)                                  AS gross_revenue,
        SUM(contribution_before_ads)                        AS contribution,
        SUM(contribution_before_ads) / SUM(gross_revenue)   AS cm,
        SUM(cost_cogs) / SUM(gross_revenue)                 AS share_cogs,
        SUM(cost_fees_tax_returns) / SUM(gross_revenue)     AS share_fees_tax_returns,
        SUM(cost_logistics_affiliates) / SUM(gross_revenue) AS share_logistics_affiliates,
        SUM(gross_revenue) / SUM(orders)                    AS avg_order_value,
        -- ads metrics: only measured days with ads actually running
        SUM(ad_spend)           FILTER (WHERE ad_measured AND ad_spend > 0) AS spend,
        SUM(attributed_revenue) FILTER (WHERE ad_measured AND ad_spend > 0) AS attributed,
        SUM(credit)                                                         AS credit,
        SUM(gross_revenue)      FILTER (WHERE ad_measured AND ad_spend > 0) AS gmv_on_ad_days
    FROM v_fct_contribution
    GROUP BY ALL
),
tgt AS (
    SELECT channel, sku_id, target_source,
           CASE target_metric WHEN 'roas' THEN target_value
                              WHEN 'acos' THEN 1.0 / target_value END AS current_target_roas
    FROM raw_internal_targets
)
SELECT
    e.*,
    x.k,
    e.attributed / NULLIF(e.spend, 0)                         AS platform_roas,
    e.spend / NULLIF(e.attributed, 0)                         AS acos,
    e.spend / NULLIF(e.gmv_on_ad_days, 0)                     AS tacos,
    CASE WHEN e.cm > 0 THEN 1.0 / (x.k * e.cm) END            AS breakeven_platform_roas,
    -- the experiment's 95% interval on k turns into a range on the break-even
    CASE WHEN e.cm > 0 THEN 1.0 / (x.k_hi * e.cm) END         AS breakeven_roas_low,
    CASE WHEN e.cm > 0 AND x.k_lo > 0 THEN 1.0 / (x.k_lo * e.cm) END AS breakeven_roas_high,
    CASE WHEN e.cm > 0 THEN x.k * e.cm END                    AS breakeven_acos,
    e.attributed * x.k                                        AS incremental_gmv,
    e.attributed * x.k * e.cm                                 AS incremental_contribution,
    e.attributed * x.k * e.cm - (e.spend - e.credit)          AS incremental_profit,
    t.current_target_roas,
    t.target_source
FROM econ e
JOIN mart_experiment_readout x USING (channel)
LEFT JOIN tgt t USING (channel, sku_id);

-- Verdict + action, kept separate so the cut-offs live in one place.
CREATE OR REPLACE TABLE mart_breakeven_actions AS
SELECT
    *,
    CASE
        WHEN cm <= 0                                   THEN 'margem_negativa'
        WHEN platform_roas >= 1.10 * breakeven_platform_roas THEN 'lucra'
        WHEN platform_roas >= 0.90 * breakeven_platform_roas THEN 'no_limite'
        ELSE 'queima'
    END AS verdict,
    CASE WHEN cm > 0 THEN ROUND(breakeven_platform_roas * 1.10, 1) END AS recommended_min_target_roas,
    CASE
        WHEN cm <= 0 THEN 'Rever preço/frete antes de anunciar: cada venda já perde dinheiro'
        WHEN platform_roas >= 1.10 * breakeven_platform_roas THEN 'Pode escalar orçamento mantendo a meta'
        WHEN breakeven_platform_roas * 1.10 <= 1.5 * platform_roas
             THEN 'Subir a meta para ' || replace(ROUND(breakeven_platform_roas * 1.10, 1)::VARCHAR, '.', ',') || 'x (entrega vai cair)'
        ELSE 'Meta de equilíbrio inalcançável hoje: pausar e medir sem ads'
    END AS action,
    CASE
        WHEN current_target_roas IS NULL THEN 'sem_meta'
        WHEN cm > 0 AND current_target_roas < breakeven_platform_roas THEN 'meta_abaixo_do_equilibrio'
        ELSE 'meta_ok'
    END AS target_check
FROM mart_sku_channel_economics;
