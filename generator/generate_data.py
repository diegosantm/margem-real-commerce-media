"""
Synthetic data generator for "Margem Real" (Ondina Skincare, a fictitious brand).

What it simulates
-----------------
* 40 SKUs sold on 4 Brazilian marketplaces: TikTok Shop, Mercado Livre, Shopee, Amazon.
* Daily orders from the brand's OMS (the financial source of truth).
* Daily ad reports exported from each platform, each with its own schema quirks:
    - TikTok Shop GMV Max (product level) + campaign settings + ROI protection credits
    - Mercado Ads Product Ads (semicolon CSV, DD/MM/YYYY, comma decimals, MLB listing ids)
    - Shopee Ads (one export overlap -> duplicated rows)
    - Amazon Sponsored Products advertised product report (two days missing)
* A go-dark holdout test: from 2026-08-17 half of the SKUs (per channel) have ads switched off.

The planted truth
-----------------
Platforms attribute to ads a share of sales that would have happened anyway (organic,
affiliate). The generator knows the true incremental revenue per real of spend (iROAS)
and writes it to data/truth/planted_truth.json. The SQL pipeline never reads that file;
validation uses it only to check that the experiment readout recovers the truth.

Everything here is fictitious. Fee levels are illustrative assumptions, not real tariffs.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 20261012
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
TRUTH = ROOT / "data" / "truth"

START, END = pd.Timestamp("2026-05-01"), pd.Timestamp("2026-09-30")
TEST_START = pd.Timestamp("2026-08-17")
AMAZON_MISSING_DAYS = [pd.Timestamp("2026-07-03"), pd.Timestamp("2026-07-04")]
SHOPEE_OVERLAP_DAYS = [pd.Timestamp("2026-06-29"), pd.Timestamp("2026-06-30"), pd.Timestamp("2026-07-01")]

CHANNELS = ["tiktok_shop", "mercado_livre", "shopee", "amazon"]

# Channel economics. ILLUSTRATIVE assumptions for a fictitious brand, not real tariffs.
CHANNEL_COSTS = pd.DataFrame(
    [
        # channel, price_index, marketplace_fee_pct, fixed_fee_per_order, seller_shipping_per_order,
        # return_rate, affiliate_order_share, affiliate_commission_pct, tax_pct, packaging_per_order
        ("tiktok_shop", 0.92, 0.10, 0.00, 6.50, 0.07, 0.35, 0.15, 0.10, 2.50),
        ("mercado_livre", 1.00, 0.16, 4.00, 9.00, 0.05, 0.00, 0.00, 0.10, 2.50),
        ("shopee", 0.95, 0.20, 4.00, 0.00, 0.05, 0.00, 0.00, 0.10, 2.50),
        ("amazon", 1.00, 0.13, 2.00, 8.00, 0.06, 0.00, 0.00, 0.10, 2.50),
    ],
    columns=[
        "channel", "price_index", "marketplace_fee_pct", "fixed_fee_per_order",
        "seller_shipping_per_order", "return_rate", "affiliate_order_share",
        "affiliate_commission_pct", "tax_pct", "packaging_per_order",
    ],
)

# Hidden behaviour of each channel's ads (the "truth").
#   share  : channel share of organic demand
#   f      : daily spend as a fraction of the SKU's expected organic revenue
#   r      : true incremental revenue per R$1 of spend (iROAS)
#   c      : share of organic revenue the platform also credits to ads
CHANNEL_TRUTH = {
    "tiktok_shop":   dict(share=0.20, f=0.10, r=1.90, c=0.40),
    "mercado_livre": dict(share=0.36, f=0.07, r=3.20, c=0.18),
    "shopee":        dict(share=0.28, f=0.08, r=2.40, c=0.22),
    "amazon":        dict(share=0.16, f=0.09, r=3.60, c=0.15),
}

CATALOG = [
    # sku_name, category, list_price
    ("Sérum Vitamina C 30ml", "Sérum", 129), ("Sérum Niacinamida 10%", "Sérum", 99),
    ("Sérum Ácido Hialurônico", "Sérum", 119), ("Sérum Retinol 0,3%", "Sérum", 149),
    ("Sérum Peptídeos", "Sérum", 169), ("Sérum Clareador", "Sérum", 139),
    ("Sérum Antioleosidade", "Sérum", 89), ("Sérum Noturno Renovador", "Sérum", 159),
    ("Protetor FPS 50 Toque Seco", "Protetor solar", 79), ("Protetor FPS 60 com Cor", "Protetor solar", 89),
    ("Protetor FPS 30 Bastão", "Protetor solar", 69), ("Protetor FPS 50 Infantil", "Protetor solar", 74),
    ("Fluido FPS 70", "Protetor solar", 99), ("Spray FPS 50", "Protetor solar", 84),
    ("Protetor Corporal FPS 50 200ml", "Protetor solar", 64),
    ("Gel-Creme Hidratante", "Hidratante", 89), ("Creme Barreira", "Hidratante", 109),
    ("Hidratante Facial Noturno", "Hidratante", 119), ("Hidratante Corporal 400ml", "Hidratante", 59),
    ("Creme de Mãos", "Hidratante", 39), ("Hidratante Labial", "Hidratante", 29),
    ("Creme Área dos Olhos", "Hidratante", 99),
    ("Gel de Limpeza 300ml", "Limpeza", 59), ("Água Micelar 400ml", "Limpeza", 49),
    ("Espuma de Limpeza", "Limpeza", 54), ("Óleo Demaquilante", "Limpeza", 79),
    ("Esfoliante Facial", "Limpeza", 64), ("Sabonete Facial em Barra", "Limpeza", 29),
    ("Kit Rotina Básica", "Kits", 239), ("Kit Vitamina C", "Kits", 279), ("Kit Verão", "Kits", 219),
    ("Kit Anti-idade", "Kits", 329), ("Kit Viagem", "Kits", 149), ("Kit Presente", "Kits", 199),
    ("Óleo Corporal", "Corpo", 89), ("Loção Firmadora", "Corpo", 99), ("Desodorante Natural", "Corpo", 34),
    ("Esfoliante Corporal", "Corpo", 69), ("Body Splash", "Corpo", 79), ("Creme para os Pés", "Corpo", 44),
]
COGS_PCT = {"Sérum": 0.20, "Protetor solar": 0.26, "Hidratante": 0.24, "Limpeza": 0.28, "Kits": 0.30, "Corpo": 0.27}
CAT_CODE = {"Sérum": "SER", "Protetor solar": "SOL", "Hidratante": "HID", "Limpeza": "LIM", "Kits": "KIT", "Corpo": "CRP"}


def season_factor(day: pd.Timestamp, channel: str) -> float:
    """Trend + weekday + Brazilian retail calendar (Dia das Mães, double dates, Dia do Cliente)."""
    i = (day - START).days
    f = 1 + 0.0012 * i
    f *= [1.02, 1.00, 1.00, 1.02, 1.05, 0.95, 0.96][day.weekday()]
    if pd.Timestamp("2026-05-03") <= day <= pd.Timestamp("2026-05-09"):
        f *= 1.35
    if day.month == day.day and day.month in (6, 7, 8, 9):  # 6.6, 7.7, 8.8, 9.9
        f *= 1.9 if channel in ("tiktok_shop", "shopee") else 1.4
    if day == pd.Timestamp("2026-09-15"):
        f *= 1.3
    return f


def main() -> None:
    rng = np.random.default_rng(SEED)
    RAW.mkdir(parents=True, exist_ok=True)
    TRUTH.mkdir(parents=True, exist_ok=True)
    days = pd.date_range(START, END, freq="D")

    # ---------------- catalog ----------------
    cat_rows, counters = [], {}
    for name, cat, price in CATALOG:
        counters[cat] = counters.get(cat, 0) + 1
        sku = f"OND-{CAT_CODE[cat]}-{counters[cat]:02d}"
        cogs = round(price * (COGS_PCT[cat] + rng.normal(0, 0.02)), 2)
        cat_rows.append((sku, name, cat, float(price), cogs))
    catalog = pd.DataFrame(cat_rows, columns=["sku_id", "sku_name", "category", "list_price", "unit_cogs"])
    n_sku = len(catalog)

    # SKU-level latent traits
    popularity = (2000 / catalog["list_price"].to_numpy()) * rng.lognormal(0, 0.40, n_sku)  # units/day, all channels
    sku_drift = rng.normal(0, 0.10, n_sku)          # SKU-specific trend over the whole window
    ad_intensity = rng.lognormal(0, 0.30, n_sku)    # how hard each SKU is pushed
    ad_quality = rng.lognormal(0, 0.25, n_sku)
    ad_quality /= ad_quality.mean()                 # SKU heterogeneity in incrementality

    costs = CHANNEL_COSTS.set_index("channel")

    # ---------------- experiment assignment (stratified pairs, per channel) ----------------
    assign_rows = []
    arm = {}
    for ch in CHANNELS:
        order = np.argsort(-popularity * catalog["list_price"].to_numpy())
        for p in range(0, n_sku, 2):
            pair = order[p:p + 2]
            dark = rng.choice(pair)
            for j in pair:
                a = "dark" if j == dark else "on"
                arm[(ch, j)] = a
                assign_rows.append((ch, catalog.sku_id[j], a, TEST_START.date(), END.date()))
    assignment = pd.DataFrame(assign_rows, columns=["channel", "sku_id", "arm", "test_start", "test_end"])

    # ---------------- daily simulation ----------------
    oms, ads, cf = [], [], []  # cf = counterfactual ledger for dark SKUs (truth only)
    n_days = len(days)
    for ch in CHANNELS:
        t = CHANNEL_TRUTH[ch]
        pidx = costs.loc[ch, "price_index"]
        for j in range(n_sku):
            price = round(catalog.list_price[j] * pidx, 2)
            day_noise = rng.lognormal(0, 0.12, n_days)
            spend_noise = rng.lognormal(0, 0.15, n_days)
            claim_noise = rng.lognormal(0, 0.10, n_days)
            for d_i, day in enumerate(days):
                frac = d_i / (n_days - 1)
                lam_units = popularity[j] * t["share"] * season_factor(day, ch) * (1 + sku_drift[j] * frac) * day_noise[d_i]
                organic_units = rng.poisson(lam_units)
                organic_rev = organic_units * price

                expected_org_rev = lam_units / day_noise[d_i] * price
                planned_spend = t["f"] * ad_intensity[j] * expected_org_rev * spend_noise[d_i]
                ads_on = not (day >= TEST_START and arm[(ch, j)] == "dark")
                inc_rev_expected = t["r"] * ad_quality[j] * planned_spend

                if ads_on:
                    spend = round(planned_spend, 2)
                    inc_units = rng.poisson(inc_rev_expected / price)
                    inc_rev = inc_units * price
                    attributed = inc_rev + t["c"] * organic_rev * claim_noise[d_i]
                else:
                    spend, inc_units, attributed = 0.0, 0, 0.0
                    if day >= TEST_START:
                        cf.append((ch, j, planned_spend, inc_rev_expected,
                                   inc_rev_expected + t["c"] * expected_org_rev))

                orders = organic_units + inc_units
                extra_units = rng.poisson(0.08 * orders) if orders else 0
                units = orders + extra_units
                gross = round(units * price, 2)
                returned_units = rng.binomial(units, costs.loc[ch, "return_rate"]) if units else 0
                refunds = round(returned_units * price, 2)
                aff_share = costs.loc[ch, "affiliate_order_share"]
                aff_gmv = round(gross * aff_share * rng.uniform(0.85, 1.15), 2) if aff_share else 0.0
                aff_comm = round(aff_gmv * costs.loc[ch, "affiliate_commission_pct"], 2)
                oms.append((day.date(), ch, catalog.sku_id[j], int(orders), int(units), gross, refunds, aff_gmv, aff_comm))
                if ads_on:
                    ads.append((day, ch, j, spend, round(attributed, 2), price))

    oms_df = pd.DataFrame(oms, columns=["order_date", "channel", "sku_id", "orders", "units", "gross_revenue",
                                        "refunded_revenue", "affiliate_gmv", "affiliate_commission"])
    ads_df = pd.DataFrame(ads, columns=["day", "channel", "j", "spend", "attributed", "price"])
    ads_df["sku_id"] = catalog.sku_id.to_numpy()[ads_df.j]
    ads_df["category"] = catalog.category.to_numpy()[ads_df.j]
    ads_df["attr_orders"] = np.maximum(0, np.round(ads_df.attributed / ads_df.price)).astype(int)

    # ---------------- TikTok Shop: GMV Max product report + settings + credits ----------------
    tk = ads_df[ads_df.channel == "tiktok_shop"].copy()
    camp_ids = {c: f"1800{i:011d}" for i, c in enumerate(COGS_PCT, start=73001)}
    tk["campaign_id"] = tk.category.map(camp_ids)
    tk["campaign_name"] = "GMVMAX_PRODUCT_" + tk.category.map(CAT_CODE)
    # campaign-day shock on the attributed number (algorithm volatility)
    shock_keys = tk[["day", "campaign_id"]].drop_duplicates()
    shock_keys["shock"] = rng.lognormal(-0.02, 0.20, len(shock_keys))
    tk = tk.merge(shock_keys, on=["day", "campaign_id"])
    tk["attributed"] = (tk.attributed * tk.shock).round(2)
    tk["attr_orders"] = np.maximum(0, np.round(tk.attributed / tk.price)).astype(int)
    tk["product_id"] = "17" + tk.j.map(lambda x: f"{3290000000000000 + x * 7919:016d}")
    tk_report = pd.DataFrame({
        "stat_date": tk.day.dt.strftime("%Y-%m-%d"), "campaign_id": tk.campaign_id, "campaign_name": tk.campaign_name,
        "product_id": tk.product_id, "cost": tk.spend, "gross_revenue": tk.attributed, "orders": tk.attr_orders,
        "roi": np.where(tk.spend > 0, (tk.attributed / tk.spend).round(2), 0.0),
    }).sort_values(["stat_date", "campaign_id", "product_id"])

    # the team set each campaign's Target ROI near its historical ROI (first 30 days), +/- 8%
    hist = tk[tk.day < START + pd.Timedelta(days=30)].groupby("campaign_id")[["attributed", "spend"]].sum()
    targets = {c: round(float(hist.loc[c, "attributed"] / hist.loc[c, "spend"] * rng.uniform(0.92, 1.08)), 1)
               for c in camp_ids.values()}
    settings = shock_keys[["day", "campaign_id"]].copy()
    settings["target_roi"] = settings.campaign_id.map(targets)
    # some days the team nudged the target mid-day (voids ROI protection for that day)
    settings["manual_target_roi_edits"] = rng.choice([0, 1, 2], size=len(settings), p=[0.86, 0.10, 0.04])
    settings = settings.sort_values(["day", "campaign_id"])

    # platform-issued credits (the "statement"); SQL recomputes these independently
    cday = tk.groupby(["day", "campaign_id"], as_index=False).agg(cost=("spend", "sum"), rev=("attributed", "sum"),
                                                                 orders=("attr_orders", "sum"))
    cday = cday.merge(settings, on=["day", "campaign_id"])
    cday["roi"] = cday.rev / cday.cost
    elig = (cday.roi < 0.9 * cday.target_roi) & (cday.orders > 20) & (cday.manual_target_roi_edits == 0)
    cday["credit"] = np.where(elig, cday.cost - cday.rev / (cday.target_roi * 0.9), 0.0).round(2)
    credits = cday[cday.credit > 0][["day", "campaign_id", "credit"]].rename(columns={"credit": "credit_amount"})

    tk_settings = settings.assign(stat_date=settings.day.dt.strftime("%Y-%m-%d"))[
        ["stat_date", "campaign_id", "target_roi", "manual_target_roi_edits"]]
    tk_credits = credits.assign(stat_date=credits.day.dt.strftime("%Y-%m-%d"))[["stat_date", "campaign_id", "credit_amount"]]

    # ---------------- Mercado Ads (BR export: ';' + DD/MM/YYYY + decimal comma) ----------------
    ml = ads_df[ads_df.channel == "mercado_livre"].copy()
    ml_listing = {j: [f"MLB{4100000000 + j * 37:d}"] for j in range(n_sku)}
    for j in (0, 3, 28):  # these SKUs have a classic + a premium listing
        ml_listing[j].append(f"MLB{4200000000 + j * 41:d}")
    rows = []
    for r in ml.itertuples():
        ids = ml_listing[r.j]
        split = [1.0] if len(ids) == 1 else [0.62, 0.38]
        for lid, s in zip(ids, split):
            spend = round(r.spend * s, 2)
            clicks = max(1, int(round(spend / rng.uniform(0.55, 1.10))))
            rows.append((r.day.strftime("%d/%m/%Y"), lid, int(clicks * rng.uniform(28, 60)), clicks, spend,
                         round(r.attributed * s, 2), int(round(r.attr_orders * s))))
    ml_report = pd.DataFrame(rows, columns=["data", "id_anuncio", "impressoes", "cliques", "investimento", "receita", "vendas"])
    for col in ("investimento", "receita"):
        ml_report[col] = ml_report[col].map(lambda v: f"{v:.2f}".replace(".", ","))

    # ---------------- Shopee Ads (one export overlap duplicates 3 days) ----------------
    sp = ads_df[ads_df.channel == "shopee"].copy()
    sp_item = {j: str(22000000000 + j * 1013) for j in range(n_sku)}
    sp_method = {j: ("GMV Max Custom ROAS" if j % 4 else "GMV Max Auto Bidding") for j in range(n_sku)}
    sp_target = {j: (round(float(rng.uniform(4.5, 7.0)), 1) if sp_method[j] == "GMV Max Custom ROAS" else None)
                 for j in range(n_sku)}
    sp_report = pd.DataFrame({
        "date": sp.day.dt.strftime("%Y-%m-%d"), "item_id": sp.j.map(sp_item), "bidding_method": sp.j.map(sp_method),
        "roas_target": sp.j.map(sp_target), "expense": sp.spend, "gmv": sp.attributed, "orders": sp.attr_orders,
    })
    dup = sp_report[pd.to_datetime(sp_report.date).isin(SHOPEE_OVERLAP_DAYS)]
    sp_report = pd.concat([sp_report, dup]).sort_values(["date", "item_id"]).reset_index(drop=True)

    # ---------------- Amazon SP advertised product report (2 days missing) ----------------
    am = ads_df[(ads_df.channel == "amazon") & (~ads_df.day.isin(AMAZON_MISSING_DAYS))].copy()
    am_asin = {j: f"B0{chr(65 + j % 26)}{(j * 7919 + 48611) % 10**7:07d}" for j in range(n_sku)}
    am_report = pd.DataFrame({
        "date": am.day.dt.strftime("%Y-%m-%d"), "campaignName": "SP | " + am.category + " | Auto+Manual",
        "advertisedSku": am.sku_id, "advertisedAsin": am.j.map(am_asin), "cost": am.spend,
        "sales7d": am.attributed, "purchases7d": am.attr_orders,
    })

    # ---------------- listing map ----------------
    lm = [("tiktok_shop", "17" + f"{3290000000000000 + j * 7919:016d}", catalog.sku_id[j]) for j in range(n_sku)]
    lm += [("mercado_livre", lid, catalog.sku_id[j]) for j in range(n_sku) for lid in ml_listing[j]]
    lm += [("shopee", sp_item[j], catalog.sku_id[j]) for j in range(n_sku)]
    lm += [("amazon", am_asin[j], catalog.sku_id[j]) for j in range(n_sku)]
    listing_map = pd.DataFrame(lm, columns=["channel", "external_id", "sku_id"])

    # ---------------- internal targets the team currently runs ----------------
    tg = []
    for j in range(n_sku):
        sku = catalog.sku_id[j]
        tg.append(("tiktok_shop", sku, "roas", targets[camp_ids[catalog.category[j]]], "GMV Max Target ROI (campanha)"))
        tg.append(("mercado_livre", sku, "acos", 0.20, "Meta interna do time"))
        if sp_target[j] is not None:
            tg.append(("shopee", sku, "roas", sp_target[j], "GMV Max Custom ROAS"))
        else:
            tg.append(("shopee", sku, "roas", None, "GMV Max Auto Bidding (sem meta)"))
        tg.append(("amazon", sku, "acos", 0.22, "Meta interna do time"))
    internal_targets = pd.DataFrame(tg, columns=["channel", "sku_id", "target_metric", "target_value", "target_source"])

    # ---------------- write raw files ----------------
    catalog.to_csv(RAW / "raw_sku_catalog.csv", index=False)
    CHANNEL_COSTS.to_csv(RAW / "raw_channel_cost_assumptions.csv", index=False)
    oms_df.to_csv(RAW / "raw_oms_orders_daily.csv", index=False)
    assignment.to_csv(RAW / "raw_experiment_assignment.csv", index=False)
    listing_map.to_csv(RAW / "raw_listing_map.csv", index=False)
    internal_targets.to_csv(RAW / "raw_internal_targets.csv", index=False)
    tk_report.to_csv(RAW / "raw_tiktok_gmvmax_product_daily.csv", index=False)
    tk_settings.to_csv(RAW / "raw_tiktok_campaign_settings_daily.csv", index=False)
    tk_credits.to_csv(RAW / "raw_tiktok_roi_protection_credits.csv", index=False)
    ml_report.to_csv(RAW / "raw_mercadoads_product_ads.csv", index=False, sep=";")
    sp_report.to_csv(RAW / "raw_shopee_ads_product.csv", index=False)
    am_report.to_csv(RAW / "raw_amazon_sp_advertised_product.csv", index=False)

    # ---------------- planted truth (never read by the SQL pipeline) ----------------
    cf_df = pd.DataFrame(cf, columns=["channel", "j", "spend", "inc_rev", "attributed"])
    truth = {"note": "Generator ground truth for the dark SKUs during the test window. "
                     "Used only by validation (recovery test).",
             "channels": {}}
    for ch in CHANNELS:
        s = cf_df[cf_df.channel == ch]
        truth["channels"][ch] = {
            "true_iroas": round(float(s.inc_rev.sum() / s.spend.sum()), 4),
            "true_incrementality_k": round(float(s.inc_rev.sum() / s.attributed.sum()), 4),
            "param_r": CHANNEL_TRUTH[ch]["r"], "param_c": CHANNEL_TRUTH[ch]["c"],
        }
    (TRUTH / "planted_truth.json").write_text(json.dumps(truth, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"OMS rows: {len(oms_df):,} | ad rows: TikTok {len(tk_report):,}, Mercado {len(ml_report):,}, "
          f"Shopee {len(sp_report):,}, Amazon {len(am_report):,} | credits: {len(tk_credits)}")
    print(json.dumps(truth["channels"], indent=1))


if __name__ == "__main__":
    main()
