-- =====================================================================
-- 04_mart_experiment.sql  |  Go-dark holdout readout.
--
-- Design: per channel, SKUs were paired by size and one of each pair had
-- ads switched off from 2026-08-17 ("dark"). The other kept running ("on").
--
-- Ratio estimator (difference-in-differences on per-day means):
--   R_x       = sum(on.test_x) / sum(on.pre_x)            trend of the "on" group
--   lost_gmv  = sum(dark.pre_gmv * R_gmv - dark.test_gmv)  GMV the dark SKUs stopped making
--   spend_cf  = sum(dark.pre_spend * R_spend)              spend they would have had
--   attr_cf   = sum(dark.pre_attr  * R_attr)               what the platform would have credited
--   iROAS     = lost_gmv / spend_cf
--   k         = lost_gmv / attr_cf    -> share of platform-attributed GMV that is incremental
--
-- Uncertainty: leave-one-SKU-out jackknife, 95% normal interval.
-- Daily means use only measured days (AVG ignores NULL = "sem medida").
-- =====================================================================

CREATE OR REPLACE TABLE int_experiment_sku AS
SELECT
    channel, sku_id, arm,
    AVG(gross_revenue)      FILTER (WHERE period = 'pre')  AS pre_gmv,
    AVG(gross_revenue)      FILTER (WHERE period = 'test') AS test_gmv,
    AVG(ad_spend)           FILTER (WHERE period = 'pre')  AS pre_spend,
    AVG(ad_spend)           FILTER (WHERE period = 'test') AS test_spend,
    AVG(attributed_revenue) FILTER (WHERE period = 'pre')  AS pre_attr,
    AVG(attributed_revenue) FILTER (WHERE period = 'test') AS test_attr
FROM fct_sku_channel_day
GROUP BY ALL;

-- Every estimate below is computed for a "sample": the full sample (left_out = NULL)
-- plus one sample per left-out SKU. Same SQL, so the jackknife cannot drift
-- from the point estimate.
CREATE OR REPLACE TABLE int_experiment_samples AS
WITH samples AS (
    SELECT DISTINCT channel, NULL::VARCHAR AS left_out FROM int_experiment_sku
    UNION ALL
    SELECT channel, sku_id FROM int_experiment_sku
),
ratios AS (
    SELECT s.channel, s.left_out,
           SUM(e.test_gmv)   / SUM(e.pre_gmv)   AS r_gmv,
           SUM(e.test_spend) / SUM(e.pre_spend) AS r_spend,
           SUM(e.test_attr)  / SUM(e.pre_attr)  AS r_attr
    FROM samples s
    JOIN int_experiment_sku e
      ON e.channel = s.channel AND e.arm = 'on'
     AND (s.left_out IS NULL OR e.sku_id <> s.left_out)
    GROUP BY ALL
),
dark AS (
    SELECT r.channel, r.left_out, r.r_gmv, r.r_spend, r.r_attr,
           SUM(e.pre_gmv * r.r_gmv - e.test_gmv) AS lost_gmv_per_day,
           SUM(e.pre_spend * r.r_spend)          AS spend_cf_per_day,
           SUM(e.pre_attr * r.r_attr)            AS attr_cf_per_day,
           COUNT(*)                              AS n_dark
    FROM ratios r
    JOIN int_experiment_sku e
      ON e.channel = r.channel AND e.arm = 'dark'
     AND (r.left_out IS NULL OR e.sku_id <> r.left_out)
    GROUP BY ALL
)
SELECT *,
       lost_gmv_per_day / spend_cf_per_day AS iroas,
       lost_gmv_per_day / attr_cf_per_day  AS k,
       attr_cf_per_day / spend_cf_per_day  AS platform_roas_cf
FROM dark;

CREATE OR REPLACE TABLE mart_experiment_readout AS
WITH pt AS (SELECT * FROM int_experiment_samples WHERE left_out IS NULL),
loo AS (
    SELECT channel, iroas, k,
           AVG(iroas) OVER (PARTITION BY channel) AS iroas_bar,
           AVG(k)     OVER (PARTITION BY channel) AS k_bar
    FROM int_experiment_samples
    WHERE left_out IS NOT NULL
),
jk AS (
    SELECT channel,
           COUNT(*)                          AS n_jk,
           SUM(POWER(iroas - iroas_bar, 2))  AS ss_iroas,
           SUM(POWER(k - k_bar, 2))          AS ss_k
    FROM loo
    GROUP BY channel
),
arms AS (
    SELECT channel,
           COUNT(*) FILTER (WHERE arm = 'dark') AS n_sku_dark,
           COUNT(*) FILTER (WHERE arm = 'on')   AS n_sku_on,
           SUM(pre_gmv) FILTER (WHERE arm = 'dark') / SUM(pre_gmv) FILTER (WHERE arm = 'on') AS pre_balance_ratio
    FROM int_experiment_sku GROUP BY channel
)
SELECT
    pt.channel,
    a.n_sku_dark, a.n_sku_on, a.pre_balance_ratio,
    pt.r_gmv, pt.lost_gmv_per_day, pt.spend_cf_per_day, pt.attr_cf_per_day,
    pt.platform_roas_cf,
    pt.iroas,
    SQRT((jk.n_jk - 1.0) / jk.n_jk * jk.ss_iroas)                 AS iroas_se,
    pt.iroas - 1.96 * SQRT((jk.n_jk - 1.0) / jk.n_jk * jk.ss_iroas) AS iroas_lo,
    pt.iroas + 1.96 * SQRT((jk.n_jk - 1.0) / jk.n_jk * jk.ss_iroas) AS iroas_hi,
    pt.k,
    SQRT((jk.n_jk - 1.0) / jk.n_jk * jk.ss_k)                     AS k_se,
    pt.k - 1.96 * SQRT((jk.n_jk - 1.0) / jk.n_jk * jk.ss_k)       AS k_lo,
    pt.k + 1.96 * SQRT((jk.n_jk - 1.0) / jk.n_jk * jk.ss_k)       AS k_hi
FROM pt
JOIN jk   USING (channel)
JOIN arms a USING (channel);
