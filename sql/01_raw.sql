-- =====================================================================
-- 01_raw.sql  |  Land every export exactly as it arrives. No business logic.
-- Each platform keeps its own column names, formats and quirks here;
-- staging is where they get normalized.
-- =====================================================================

-- Master data ----------------------------------------------------------
CREATE OR REPLACE TABLE raw_sku_catalog AS
SELECT * FROM read_csv('data/raw/raw_sku_catalog.csv', header = true);

CREATE OR REPLACE TABLE raw_channel_cost_assumptions AS
SELECT * FROM read_csv('data/raw/raw_channel_cost_assumptions.csv', header = true);

CREATE OR REPLACE TABLE raw_listing_map AS
SELECT * FROM read_csv('data/raw/raw_listing_map.csv', header = true,
                       types = {'external_id': 'VARCHAR'});

CREATE OR REPLACE TABLE raw_experiment_assignment AS
SELECT * FROM read_csv('data/raw/raw_experiment_assignment.csv', header = true);

CREATE OR REPLACE TABLE raw_internal_targets AS
SELECT * FROM read_csv('data/raw/raw_internal_targets.csv', header = true);

-- Financial source of truth (brand OMS) --------------------------------
CREATE OR REPLACE TABLE raw_oms_orders_daily AS
SELECT * FROM read_csv('data/raw/raw_oms_orders_daily.csv', header = true);

-- TikTok Shop | GMV Max (product level), settings and ROI protection ----
CREATE OR REPLACE TABLE raw_tiktok_gmvmax_product_daily AS
SELECT * FROM read_csv('data/raw/raw_tiktok_gmvmax_product_daily.csv', header = true,
                       types = {'campaign_id': 'VARCHAR', 'product_id': 'VARCHAR'});

CREATE OR REPLACE TABLE raw_tiktok_campaign_settings_daily AS
SELECT * FROM read_csv('data/raw/raw_tiktok_campaign_settings_daily.csv', header = true,
                       types = {'campaign_id': 'VARCHAR'});

CREATE OR REPLACE TABLE raw_tiktok_roi_protection_credits AS
SELECT * FROM read_csv('data/raw/raw_tiktok_roi_protection_credits.csv', header = true,
                       types = {'campaign_id': 'VARCHAR'});

-- Mercado Ads | Brazilian export: ';' separator, DD/MM/YYYY, decimal comma.
-- Landed as text on purpose: parsing is a staging decision, not a load accident.
CREATE OR REPLACE TABLE raw_mercadoads_product_ads AS
SELECT * FROM read_csv('data/raw/raw_mercadoads_product_ads.csv', header = true,
                       delim = ';', all_varchar = true);

-- Shopee Ads | contains an overlapping re-download (duplicated days) -----
CREATE OR REPLACE TABLE raw_shopee_ads_product AS
SELECT * FROM read_csv('data/raw/raw_shopee_ads_product.csv', header = true,
                       types = {'item_id': 'VARCHAR'});

-- Amazon Sponsored Products | advertised product report ---------------
CREATE OR REPLACE TABLE raw_amazon_sp_advertised_product AS
SELECT * FROM read_csv('data/raw/raw_amazon_sp_advertised_product.csv', header = true);
