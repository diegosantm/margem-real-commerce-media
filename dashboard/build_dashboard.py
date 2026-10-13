"""
Build docs/index.html (single file, opens offline, served by GitHub Pages).

Python ships the base ROW BY ROW plus configuration and the SQL marts.
The browser recomputes every number from the rows; the SQL marts are embedded
only so the page can cross-check itself (SQL x JavaScript table at the bottom).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
con = duckdb.connect(str(ROOT / "warehouse" / "margem_real.duckdb"), read_only=True)


def records(sql: str) -> list[dict]:
    cur = con.execute(sql)
    cols = [c[0] for c in cur.description]
    out = []
    for row in cur.fetchall():
        rec = {}
        for c, v in zip(cols, row):
            if isinstance(v, (dt.date, dt.datetime)):
                v = v.isoformat()[:10]
            rec[c] = v
        out.append(rec)
    return out


CHANNELS = [("tiktok_shop", "TikTok Shop"), ("mercado_livre", "Mercado Livre"), ("shopee", "Shopee"), ("amazon", "Amazon")]
CH_IDX = {c: i for i, (c, _) in enumerate(CHANNELS)}

skus = records("SELECT sku_id, sku_name, category, list_price, unit_cogs FROM dim_sku ORDER BY sku_id")
SKU_IDX = {s["sku_id"]: i for i, s in enumerate(skus)}
cats = sorted({s["category"] for s in skus}, key=lambda c: ["Sérum", "Protetor solar", "Hidratante", "Limpeza", "Kits", "Corpo"].index(c))
EPOCH = dt.date(1970, 1, 1)

# rows: [0 day, 1 ch, 2 sku, 3 arm(0 on / 1 dark), 4 orders, 5 units, 6 gross, 7 refunds,
#        8 affComm, 9 spend(-1 = sem medida), 10 attr(-1 = sem medida), 11 credit]
rows = []
for r in con.execute("""
    SELECT d, channel, sku_id, arm, orders, units, gross_revenue, refunded_revenue, affiliate_commission,
           ad_spend, attributed_revenue, credit
    FROM fct_sku_channel_day ORDER BY d, channel, sku_id""").fetchall():
    d, ch, sku, arm, orders, units, gross, ref, aff, spend, attr, credit = r
    rows.append([(d - EPOCH).days, CH_IDX[ch], SKU_IDX[sku], 1 if arm == "dark" else 0, orders, units,
                 round(gross, 2), round(ref, 2), round(aff, 2),
                 -1 if spend is None else round(spend, 2), -1 if attr is None else round(attr, 2), round(credit, 4)])

rows_json = json.dumps(rows, separators=(",", ":"))
fp = hashlib.sha256(rows_json.encode()).hexdigest()[:8]

ch_params = {r["channel"]: r for r in records("SELECT * FROM dim_channel")}
targets = records("SELECT channel, sku_id, target_metric, target_value, target_source FROM raw_internal_targets")

sql = {
    "exp": {r["channel"]: r for r in records("SELECT * FROM mart_experiment_readout")},
    "score": {r["channel"]: r for r in records("SELECT * FROM mart_channel_scorecard")},
    "econ": records("SELECT channel, sku_id, cm, k, platform_roas, breakeven_platform_roas, breakeven_roas_low, "
                    "breakeven_roas_high, incremental_profit, verdict, action, recommended_min_target_roas, "
                    "current_target_roas, target_source, target_check FROM mart_breakeven_actions"),
    "roiProt": records("SELECT ad_date, campaign_id, cost, gross_revenue, orders, roi, target_roi, "
                       "manual_target_roi_edits, protection_status, credit_recomputed, credit_statement "
                       "FROM fct_tiktok_campaign_day ORDER BY ad_date, campaign_id"),
    "campaigns": records("SELECT DISTINCT t.campaign_id, s.category FROM stg_ads_tiktok t "
                         "JOIN dim_sku s USING (sku_id) ORDER BY 1"),
    "cleaning": records("SELECT * FROM stg_cleaning_log"),
    "totals": records("SELECT COUNT(*) AS n, SUM(gross_revenue) AS gross FROM fct_sku_channel_day")[0],
}
truth = json.loads((ROOT / "data" / "truth" / "planted_truth.json").read_text(encoding="utf-8"))["channels"]
validation = json.loads((ROOT / "validation" / "validation_results.json").read_text(encoding="utf-8"))

data = {
    "meta": {"start": "2026-05-01", "testStart": "2026-08-17", "end": "2026-09-30",
             "testStartDay": (dt.date(2026, 8, 17) - EPOCH).days, "fp": fp,
             "built": dt.date.today().isoformat(), "nRows": len(rows)},
    "channels": [{"id": c, "label": l} for c, l in CHANNELS],
    "skus": [{"id": s["sku_id"], "name": s["sku_name"], "cat": cats.index(s["category"]), "cogs": s["unit_cogs"]} for s in skus],
    "cats": cats,
    "chParams": [ch_params[c] for c, _ in CHANNELS],
    "targets": targets,
    "sql": sql,
    "truth": truth,
    "validation": validation,
}

data["rows"] = "__ROWS__"
payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False).replace('"__ROWS__"', rows_json)

template = (ROOT / "dashboard" / "template.html").read_text(encoding="utf-8")
html = template.replace("/*__DATA__*/null", payload)
out = ROOT / "docs" / "index.html"
out.parent.mkdir(exist_ok=True)
out.write_text(html, encoding="utf-8")
print(f"dashboard: {out.relative_to(ROOT)} ({out.stat().st_size / 1e6:.2f} MB, {len(rows):,} rows, fp {fp})")
