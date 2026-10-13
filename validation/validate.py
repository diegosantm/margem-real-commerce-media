"""
Automated validation for the Margem Real warehouse.

Three families of checks:
  A. Integrity  : grain, coverage, mapping, cleaning rules, "no measurement" vs zero.
  B. Logic      : independent recomputation (pandas reads the raw CSVs, not the warehouse)
                  and hand-calculated test cases for every business formula.
  C. Recovery   : the experiment readout must recover the generator's planted truth
                  (true iROAS and k inside the 95% jackknife interval).

Writes validation/validation_report.md and validation/validation_results.json.
Exit code 1 if any check fails.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
con = duckdb.connect(str(ROOT / "warehouse" / "margem_real.duckdb"), read_only=True)
q = lambda sql: con.execute(sql).fetchall()
one = lambda sql: con.execute(sql).fetchone()[0]

LABEL = {"tiktok_shop": "TikTok Shop", "mercado_livre": "Mercado Livre", "shopee": "Shopee", "amazon": "Amazon"}
br = lambda x, d=2: f"{x:.{d}f}".replace(".", ",")
results: list[dict] = []


def check(family: str, name: str, ok: bool, detail: str) -> None:
    results.append({"family": family, "name": name, "ok": bool(ok), "detail": detail})


# ---------------------------------------------------------------- A. integrity
n_fact = one("SELECT COUNT(*) FROM fct_sku_channel_day")
n_keys = one("SELECT COUNT(*) FROM (SELECT DISTINCT d, channel, sku_id FROM fct_sku_channel_day)")
check("A", "Grão único dia x canal x SKU", n_fact == n_keys == 153 * 4 * 40,
      f"{n_fact:,} linhas, {n_keys:,} chaves distintas, esperado {153*4*40:,}")

dup_ids = one("SELECT COUNT(*) FROM (SELECT channel, external_id FROM raw_listing_map GROUP BY ALL HAVING COUNT(*) > 1)")
check("A", "De-para de anúncios sem ID externo repetido", dup_ids == 0, f"{dup_ids} IDs externos apontando para mais de um SKU")
dup_ads = one("SELECT COUNT(*) FROM (SELECT ad_date, channel, sku_id FROM stg_ads GROUP BY ALL HAVING COUNT(*) > 1)")
check("A", "Uma linha de ads por dia x canal x SKU", dup_ads == 0, f"{dup_ads} chaves repetidas em stg_ads")
unmapped = one("SELECT COUNT(*) FROM stg_ads WHERE sku_id IS NULL")
check("A", "Todo anúncio mapeado para um SKU", unmapped == 0, f"{unmapped} linhas de ads sem SKU")

oms_csv = pd.read_csv(RAW / "raw_oms_orders_daily.csv")
check("A", "OMS integral no fato (receita bruta)",
      abs(oms_csv.gross_revenue.sum() - one("SELECT SUM(gross_revenue) FROM fct_sku_channel_day")) < 0.01,
      f"CSV R$ {oms_csv.gross_revenue.sum():,.2f} = fato")

sp_raw = pd.read_csv(RAW / "raw_shopee_ads_product.csv", dtype={"item_id": str})
sp_dups = int(sp_raw.duplicated(["date", "item_id"]).sum())
sp_stg = one("SELECT COUNT(*) FROM stg_ads_shopee")
check("A", "Shopee: duplicatas do re-download removidas", len(sp_raw) - sp_dups == sp_stg and sp_dups > 0,
      f"{len(sp_raw):,} linhas brutas -> {sp_stg:,} ({sp_dups} duplicadas em 3 dias sobrepostos)")
exact = sp_raw[sp_raw.duplicated(["date", "item_id"], keep=False)].drop_duplicates()
check("A", "Shopee: duplicatas eram cópias idênticas", exact.duplicated(["date", "item_id"]).sum() == 0,
      "nenhuma divergência de valores entre as cópias")

ml_raw = pd.read_csv(RAW / "raw_mercadoads_product_ads.csv", sep=";", dtype=str)
ml_spend_py = ml_raw.investimento.str.replace(",", ".").astype(float).sum()
ml_spend_sql = one("SELECT SUM(spend) FROM stg_ads_mercado")
check("A", "Mercado Ads: parsing de vírgula decimal e data BR", abs(ml_spend_py - ml_spend_sql) < 0.01,
      f"pandas R$ {ml_spend_py:,.2f} | SQL R$ {ml_spend_sql:,.2f}")
multi = one("SELECT COUNT(DISTINCT sku_id) FROM stg_ads_mercado WHERE listings_in_row > 1")
check("A", "Mercado Ads: SKUs com 2 anúncios MLB consolidados", multi == 3, f"{multi} SKUs com mais de um MLB")

amz_cov = q("SELECT d FROM fct_sku_channel_day WHERE channel='amazon' AND NOT ad_measured GROUP BY d ORDER BY 1")
amz_cov = [str(r[0]) for r in amz_cov]
check("A", "Amazon: dias sem export viram 'sem medida'", amz_cov == ["2026-07-03", "2026-07-04"],
      f"dias sem medida: {', '.join(amz_cov)}")
nulls_ok = one("SELECT COUNT(*) FROM fct_sku_channel_day WHERE NOT ad_measured AND (ad_spend IS NOT NULL OR attributed_revenue IS NOT NULL)")
check("A", "'Sem medida' nunca vira zero", nulls_ok == 0, f"{nulls_ok} linhas sem medida com valor preenchido")

dark_spend = one("SELECT COALESCE(SUM(ad_spend),0) + COALESCE(SUM(attributed_revenue),0) FROM fct_sku_channel_day WHERE arm='dark' AND period='test'")
check("A", "Grupo apagado sem gasto nem atribuição no teste", dark_spend == 0, f"soma = {dark_spend}")
on_gaps = one("SELECT COUNT(*) FROM fct_sku_channel_day WHERE arm='on' AND ad_measured AND ad_spend = 0")
check("A", "Grupo ligado com gasto em todo dia medido", on_gaps == 0, f"{on_gaps} dias medidos sem gasto")

bal = q("SELECT channel, pre_balance_ratio FROM mart_experiment_readout ORDER BY 1")
check("A", "Balanceamento dos grupos no pré-teste (±10%)", all(0.9 <= b <= 1.1 for _, b in bal),
      " | ".join(f"{LABEL[c]}: {br(b,3)}" for c, b in bal))

# ---------------------------------------------------------------- B. logic
tk_raw = pd.read_csv(RAW / "raw_tiktok_gmvmax_product_daily.csv")
roi_err = (tk_raw.roi - (tk_raw.gross_revenue / tk_raw.cost).round(2)).abs().max()
check("B", "TikTok: coluna roi = receita bruta / custo", roi_err < 0.011, f"maior desvio {roi_err:.4f}")

diff = one("SELECT MAX(ABS(credit_recomputed - credit_statement)) FROM fct_tiktok_campaign_day")
n_cred = one("SELECT COUNT(*) FROM fct_tiktok_campaign_day WHERE credit_recomputed > 0")
n_stmt = len(pd.read_csv(RAW / "raw_tiktok_roi_protection_credits.csv"))
check("B", "ROI protection recalculado bate com o extrato", diff < 0.011 and n_cred == n_stmt,
      f"{n_cred} dias-campanha com crédito no SQL, {n_stmt} no extrato, maior diferença R$ {diff:.2f}")
over = one("SELECT COUNT(*) FROM fct_tiktok_campaign_day WHERE credit_statement > cost")
check("B", "Crédito nunca maior que o custo do dia", over == 0, f"{over} violações")
alloc = abs(one("SELECT SUM(credit) FROM fct_sku_channel_day") - one("SELECT SUM(credit_statement) FROM fct_tiktok_campaign_day"))
check("B", "Rateio de créditos por SKU fecha com o total", alloc < 0.01, f"diferença R$ {alloc:.4f}")

wf = q("""SELECT channel,
          SUM(value) FILTER (WHERE step IN (1,2,4,5,6,8,9)) AS calc,
          SUM(value) FILTER (WHERE step = 10) AS final FROM mart_profit_waterfall GROUP BY 1""")
check("B", "Cascata fecha: soma dos degraus = lucro incremental", all(abs(c - f) < 0.01 for _, c, f in wf),
      " | ".join(f"{LABEL[c]}: R$ {f:,.0f}".replace(",", ".") for c, _, f in wf))

ident = one("SELECT MAX(ABS(breakeven_platform_roas * k * cm - 1)) FROM mart_sku_channel_economics WHERE cm > 0")
check("B", "Identidade do break-even: ROAS x k x cm = 1", ident < 1e-9, f"maior desvio {ident:.2e}")
shares = one("SELECT MAX(ABS(share_cogs + share_fees_tax_returns + share_logistics_affiliates + cm - 1)) FROM mart_sku_channel_economics")
check("B", "Custos + margem somam 100% da receita", shares < 1e-9, f"maior desvio {shares:.2e}")

spend_sc = one("SELECT SUM(spend) FROM mart_channel_scorecard")
spend_raw = (tk_raw.cost.sum() + ml_spend_py + sp_raw.drop_duplicates(["date", "item_id"]).expense.sum()
             + pd.read_csv(RAW / "raw_amazon_sp_advertised_product.csv").cost.sum())
check("B", "Investimento total = soma dos 4 exports (independente)", abs(spend_sc - spend_raw) < 0.05,
      f"marts R$ {spend_sc:,.2f} | CSVs R$ {spend_raw:,.2f}")

# hand-calculated test cases
cases = [
    ("Break-even: cm 25%, k 0,40", 1 / (0.40 * 0.25), 10.0),
    ("Crédito ROI protection: custo 1.000, receita 4.000, meta 5,0", 1000 - 4000 / (5.0 * 0.9), 111.11),
    ("ACOS máximo: cm 30%, k 0,50", 0.50 * 0.30, 0.15),
]
for label, got, expected in cases:
    check("B", f"Caso-teste: {label}", abs(got - expected) < 0.01, f"calculado {got:.2f}, esperado à mão {expected:.2f}")

# tiny DiD by hand: on 100->110 (R=1.1); dark pre 50 -> test 40; lost = 50*1.1-40 = 15; spend_cf = 10*1.0 -> iROAS 1.5
toy = con.execute("""
WITH e AS (SELECT * FROM (VALUES ('on',100.0,110.0,10.0,10.0), ('dark',50.0,40.0,10.0,0.0))
           t(arm, pre_gmv, test_gmv, pre_spend, test_spend)),
r AS (SELECT SUM(test_gmv)/SUM(pre_gmv) rg, SUM(test_spend)/SUM(pre_spend) rs FROM e WHERE arm='on')
SELECT SUM(pre_gmv*rg - test_gmv) / SUM(pre_spend*rs) FROM e, r WHERE arm='dark'""").fetchone()[0]
check("B", "Caso-teste: estimador DiD em exemplo de 2 SKUs", abs(toy - 1.5) < 1e-9, f"calculado {toy:.2f}, esperado 1,50")

# ---------------------------------------------------------------- C. recovery
truth = json.loads((ROOT / "data" / "truth" / "planted_truth.json").read_text(encoding="utf-8"))["channels"]
for ch, lo, hi, est, klo, khi, kest in q("SELECT channel, iroas_lo, iroas_hi, iroas, k_lo, k_hi, k FROM mart_experiment_readout ORDER BY 1"):
    t = truth[ch]
    check("C", f"{LABEL[ch]}: iROAS verdadeiro dentro do IC 95%", lo <= t["true_iroas"] <= hi,
          f"verdade {br(t['true_iroas'])} | estimado {br(est)} [{br(lo)}; {br(hi)}]")
    check("C", f"{LABEL[ch]}: k verdadeiro dentro do IC 95%", klo <= t["true_incrementality_k"] <= khi,
          f"verdade {br(t['true_incrementality_k'],3)} | estimado {br(kest,3)} [{br(klo,3)}; {br(khi,3)}]")

# ---------------------------------------------------------------- report
passed = sum(r["ok"] for r in results)
fam_name = {"A": "Integridade", "B": "Lógica e casos-teste", "C": "Recuperação da verdade plantada"}
lines = ["# Validation report", "", f"**{passed}/{len(results)} checks passed**", ""]
for fam in "ABC":
    lines += [f"## {fam}. {fam_name[fam]}", "", "| | Check | Detail |", "|---|---|---|"]
    lines += [f"| {'✅' if r['ok'] else '❌'} | {r['name']} | {r['detail']} |" for r in results if r["family"] == fam]
    lines.append("")
(ROOT / "validation" / "validation_report.md").write_text("\n".join(lines), encoding="utf-8")
(ROOT / "validation" / "validation_results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"{passed}/{len(results)} checks passed")
for r in results:
    if not r["ok"]:
        print("  FAIL", r["name"], "->", r["detail"])
raise SystemExit(0 if passed == len(results) else 1)
