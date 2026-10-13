-- =====================================================================
-- 02_staging.sql  |  One grain, one vocabulary.
-- Every ad source becomes (ad_date, channel, sku_id, spend,
-- attributed_revenue, attributed_orders). Platform names stay in raw.
-- =====================================================================

-- OMS ---------------------------------------------------------------
CREATE OR REPLACE TABLE stg_oms AS
SELECT
    CAST(order_date AS DATE)          AS d,
    channel,
    sku_id,
    orders,
    units,
    gross_revenue::DOUBLE             AS gross_revenue,
    refunded_revenue::DOUBLE          AS refunded_revenue,
    affiliate_commission::DOUBLE      AS affiliate_commission
FROM raw_oms_orders_daily;

-- TikTok Shop: product_id -> sku via listing map --------------------
CREATE OR REPLACE TABLE stg_ads_tiktok AS
SELECT
    CAST(r.stat_date AS DATE)         AS ad_date,
    'tiktok_shop'                     AS channel,
    m.sku_id,
    r.campaign_id,
    r.cost::DOUBLE                    AS spend,
    r.gross_revenue::DOUBLE           AS attributed_revenue,
    r.orders                          AS attributed_orders,
    r.roi                             AS platform_roi_reported
FROM raw_tiktok_gmvmax_product_daily r
LEFT JOIN raw_listing_map m
       ON m.channel = 'tiktok_shop' AND m.external_id = r.product_id;

-- Mercado Ads: parse BR formats, collapse several listings (MLB) per SKU
CREATE OR REPLACE TABLE stg_ads_mercado AS
SELECT
    strptime(r.data, '%d/%m/%Y')::DATE                         AS ad_date,
    'mercado_livre'                                            AS channel,
    m.sku_id,
    SUM(CAST(replace(r.investimento, ',', '.') AS DOUBLE))     AS spend,
    SUM(CAST(replace(r.receita, ',', '.') AS DOUBLE))          AS attributed_revenue,
    SUM(CAST(r.vendas AS INTEGER))                             AS attributed_orders,
    COUNT(*)                                                   AS listings_in_row
FROM raw_mercadoads_product_ads r
LEFT JOIN raw_listing_map m
       ON m.channel = 'mercado_livre' AND m.external_id = r.id_anuncio
GROUP BY ALL;

-- Shopee: drop the overlapping re-download (exact duplicate per date x item)
CREATE OR REPLACE TABLE stg_ads_shopee AS
SELECT
    CAST(r.date AS DATE)              AS ad_date,
    'shopee'                          AS channel,
    m.sku_id,
    r.bidding_method,
    r.roas_target,
    r.expense::DOUBLE                 AS spend,
    r.gmv::DOUBLE                     AS attributed_revenue,
    r.orders                          AS attributed_orders
FROM raw_shopee_ads_product r
LEFT JOIN raw_listing_map m
       ON m.channel = 'shopee' AND m.external_id = r.item_id
QUALIFY ROW_NUMBER() OVER (PARTITION BY r.date, r.item_id ORDER BY r.expense DESC) = 1;

-- Amazon: ASIN -> sku via listing map ---------------------------------
CREATE OR REPLACE TABLE stg_ads_amazon AS
SELECT
    CAST(r.date AS DATE)              AS ad_date,
    'amazon'                          AS channel,
    m.sku_id,
    r.advertisedSku                   AS reported_sku,
    r.cost::DOUBLE                    AS spend,
    r.sales7d::DOUBLE                 AS attributed_revenue,
    r.purchases7d                     AS attributed_orders
FROM raw_amazon_sp_advertised_product r
LEFT JOIN raw_listing_map m
       ON m.channel = 'amazon' AND m.external_id = r.advertisedAsin;

-- Unified ad fact ------------------------------------------------------
CREATE OR REPLACE TABLE stg_ads AS
SELECT ad_date, channel, sku_id, spend, attributed_revenue, attributed_orders FROM stg_ads_tiktok
UNION ALL
SELECT ad_date, channel, sku_id, spend, attributed_revenue, attributed_orders FROM stg_ads_mercado
UNION ALL
SELECT ad_date, channel, sku_id, spend, attributed_revenue, attributed_orders FROM stg_ads_shopee
UNION ALL
SELECT ad_date, channel, sku_id, spend, attributed_revenue, attributed_orders FROM stg_ads_amazon;

-- Report coverage: a channel-day is "measured" only if its export has rows.
-- A missing export is "no measurement", never "zero spend".
CREATE OR REPLACE TABLE stg_ad_report_coverage AS
SELECT DISTINCT channel, ad_date FROM stg_ads;

-- Cleaning ledger (declared in numbers on the dashboard) ---------------
CREATE OR REPLACE TABLE stg_cleaning_log AS
SELECT 'shopee' AS channel, 'Linhas duplicadas por re-download sobreposto (removidas)' AS rule,
       (SELECT COUNT(*) FROM raw_shopee_ads_product) AS rows_in,
       (SELECT COUNT(*) FROM stg_ads_shopee)         AS rows_out
UNION ALL
SELECT 'mercado_livre', 'Anúncios MLB somados por SKU (SKU com mais de um anúncio)',
       (SELECT COUNT(*) FROM raw_mercadoads_product_ads),
       (SELECT COUNT(*) FROM stg_ads_mercado)
UNION ALL
SELECT 'amazon', 'Dias sem export do relatório (tratados como sem medida)',
       (SELECT COUNT(*) FROM generate_series(DATE '2026-05-01', DATE '2026-09-30', INTERVAL 1 DAY)),
       (SELECT COUNT(DISTINCT ad_date) FROM stg_ads_amazon);
