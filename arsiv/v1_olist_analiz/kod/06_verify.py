"""Adım 6 - Bağımsız doğrulama ve ek rakamlar.

Kullanım: python3 -I 06_verify.py <ham_csv_klasoru> <cikti_klasoru>

Ana hattı (01-05) ve onun ara dosyalarını kullanmadan, doğrudan ham CSV'lerden başlayarak başlıca
rakamları yeniden hesaplar ve ana hattın ürettiği değerlerle karşılaştırır. Ayrıca yönetici özetinde
kullanılan birkaç ek rakamı üretir.
"""
import json
import os
import sys

import numpy as np
import pandas as pd

raw, out = sys.argv[1], sys.argv[2]
P = lambda f: os.path.join(raw, f)
keyf = os.path.join(out, "key_numbers.json")
key = json.load(open(keyf))
SNAP = pd.Timestamp("2018-09-01")
results = []


def chk(name, indep, main, tol=1e-9):
    ok = bool(abs(indep - main) <= tol * max(1.0, abs(main)))
    results.append(ok)
    print(f"[{'TAMAM' if ok else 'HATA '}] {name}: bağımsız = {indep:,.4f} | ana hat = {main:,.4f}")


# ----------------------------------------------------------------- ham veriden geçerli siparişler
orders = pd.read_csv(
    P("olist_orders_dataset.csv"),
    usecols=["order_id", "customer_id", "order_status", "order_purchase_timestamp",
             "order_delivered_customer_date"],
    parse_dates=["order_purchase_timestamp", "order_delivered_customer_date"],
)
cust_map = pd.read_csv(P("olist_customers_dataset.csv"), usecols=["customer_id", "customer_unique_id"])
items = pd.read_csv(P("olist_order_items_dataset.csv"), usecols=["order_id", "order_item_id"])
pay = pd.read_csv(P("olist_order_payments_dataset.csv"), usecols=["order_id", "payment_value"])
pv = pay.groupby("order_id")["payment_value"].sum()

ok = (
    ~orders["order_status"].isin(["canceled", "unavailable", "created"])
    & orders["order_id"].isin(items["order_id"].unique())
    & orders["order_id"].isin(pv.index)
    & (orders["order_purchase_timestamp"] <= pd.Timestamp("2018-08-31 23:59:59"))
)
v = orders[ok].merge(cust_map, on="customer_id", how="left")
v["value"] = v["order_id"].map(pv)
v["d"] = v["order_purchase_timestamp"].dt.normalize()
print(f"Bağımsız geçerli sipariş: {len(v):,d}\n")

# ----------------------------------------------------------------- temel sayılar
chk("geçerli sipariş sayısı", len(v), key["basket"]["orders"])
g = v.groupby("customer_unique_id")
first = g["d"].min()
last = g["d"].max()
F = g["d"].nunique()
M = g["value"].sum()
seg_main = pd.read_csv(os.path.join(out, "rfm_segments.csv"), index_col=0)
chk("benzersiz müşteri", len(first), seg_main["musteri"].sum())
chk("toplam ciro (R$)", v["value"].sum(), seg_main["ciro"].sum(), tol=1e-6)
chk("tek alışveriş günü olan müşteri payı (%)", (F == 1).mean() * 100, key["churn"]["never_returned_pct"])

# ----------------------------------------------------------------- RFM segmentleri (farklı kodla)
R = (SNAP - last).dt.days
rq = np.quantile(R, [.2, .4, .6, .8])
mq = np.quantile(M, [.2, .4, .6, .8])
r_score = 5 - np.searchsorted(rq, R.values, side="left")
m_score = 1 + np.searchsorted(mq, M.values, side="left")
f_ = F.values
seg = np.full(len(F), "Kayıp - standart", dtype=object)
seg[(r_score <= 2) & (m_score >= 4) & (f_ == 1)] = "Kayıp - yüksek değerli"
seg[(r_score == 3) & (f_ == 1)] = "Soğuyanlar"
seg[(r_score >= 4) & (f_ == 1)] = "Yeni - standart"
seg[(r_score >= 4) & (m_score >= 4) & (f_ == 1)] = "Yeni - yüksek sepet"
seg[(f_ >= 2)] = "Uyuyan sadıklar"
seg[(f_ >= 2) & (r_score >= 4)] = "Şampiyonlar"
cnt = pd.Series(seg).value_counts()
print("\nRFM segment sayıları:")
for name in seg_main.index:
    chk(f"  {name}", int(cnt.get(name, 0)), int(seg_main.loc[name, "musteri"]))
print(f"  Skor sınırları: recency {rq.tolist()} gün | monetary {[round(x, 1) for x in mq]} R$")

# ----------------------------------------------------------------- kohort tutunma (farklı kodla)
vv = v.merge(first.rename("fd"), left_on="customer_unique_id", right_index=True)
mi = lambda s: s.dt.year * 12 + s.dt.month
fm = mi(first.rename("x").to_frame()["x"]) if False else (first.dt.year * 12 + first.dt.month)
lo, hi = 2017 * 12 + 1, 2018 * 12 + 7                      # kohortlar: 2017-01 ... 2018-07
in_coh = (fm >= lo) & (fm <= hi)
sizes_total = int(in_coh.sum())
later = vv[vv["d"] > vv["fd"]].copy()
later["k"] = mi(later["d"]) - mi(later["fd"])
later["cm"] = mi(later["fd"])
later = later[later["cm"].between(lo, hi)]
m1 = later[later["k"] == 1].drop_duplicates("customer_unique_id")
chk("ağırlıklı tutunma, 1. ay (%)", len(m1) / sizes_total * 100, key["cohort"]["weighted_retention_pct"]["1"])
obs12 = in_coh & (fm + 12 <= 2018 * 12 + 8)                # 12. ayı gözlenebilen kohortlar
m12 = later[(later["k"] == 12) & (later["cm"] + 12 <= 2018 * 12 + 8)].drop_duplicates("customer_unique_id")
chk("ağırlıklı tutunma, 12. ay (%)", len(m12) / int(obs12.sum()) * 100, key["cohort"]["weighted_retention_pct"]["12"])

nxt = vv[vv["d"] > vv["fd"]].groupby("customer_unique_id")["d"].min()      # 2. alışveriş günü
gap = (nxt - first.reindex(nxt.index)).dt.days
elig = first[(first + pd.Timedelta(days=180) <= SNAP) & (first >= pd.Timestamp("2017-01-01"))]
r180 = (gap.reindex(elig.index) <= 180).mean() * 100
chk("180 günde tekrar alım, ilk alım tarihinden (%)", r180, key["cohort"]["repeat_within_days_pct"]["180"])
chk("tekrar alanlarda 2. alışverişe medyan gün", float(gap.median()), key["cohort"]["gap_stats"]["median"])
chk("tekrar alan müşteri sayısı", len(gap), key["cohort"]["gap_stats"]["repeaters"])

# ----------------------------------------------------------------- churn popülasyonu (teslimat sonrası 180 gün)
vo = v.sort_values(["customer_unique_id", "order_purchase_timestamp"])
fo = vo.drop_duplicates("customer_unique_id")
fo = fo[fo["order_delivered_customer_date"].notna()].copy()
fo["dd"] = fo["order_delivered_customer_date"].dt.normalize()
fo["second"] = fo["customer_unique_id"].map(nxt)
early = fo["second"].notna() & (fo["second"] <= fo["dd"])
fo = fo[~early]
fo = fo[(fo["dd"] >= pd.Timestamp("2017-01-01")) & (fo["dd"] + pd.Timedelta(days=180) <= SNAP)]
dtr = (fo["second"] - fo["dd"]).dt.days
y = ((dtr > 0) & (dtr <= 180))
chk("churn analiz popülasyonu", len(fo), key["churn"]["population"]["eligible"])
chk("180 günde tekrar alan sayısı", int(y.sum()), key["churn"]["population"]["positives"])
chk("180 günde tekrar alım oranı (%)", y.mean() * 100, key["churn"]["repeat_180_pct"])
chk("son alışverişi 180 günden eski müşteri payı (%)", (R > 180).mean() * 100, key["churn"]["lapsed_180_pct"])

# ----------------------------------------------------------------- sepet
ic = items[items["order_id"].isin(v["order_id"])].groupby("order_id").size()
chk("tek kalemli sipariş payı (%)", (ic == 1).mean() * 100, key["basket"]["single_item_pct"])
chk("ortalama kalem / sipariş", ic.mean(), key["basket"]["avg_items_per_order"])

# ----------------------------------------------------------------- tahmin: haftalık seri ve geriye dönük test
vw = v[v["d"] >= pd.Timestamp("2017-01-02")].copy()
vw["week"] = vw["d"] - pd.to_timedelta(vw["d"].dt.weekday, unit="D")
w = vw.groupby("week")["value"].sum()
w = w[w.index <= pd.Timestamp("2018-08-13")]
w = w.reindex(pd.date_range(w.index.min(), pd.Timestamp("2018-08-13"), freq="7D"), fill_value=0.0)
BF = pd.Timestamp("2017-11-20")
chk("Black Friday haftası cirosu (R$)", float(w.loc[BF]), key["forecast"]["bf_week_revenue"], tol=1e-9)
base_bf = np.mean([w.loc[BF - pd.Timedelta(days=14)], w.loc[BF - pd.Timedelta(days=7)]])
chk("Black Friday çarpanı", float(w.loc[BF] / base_bf), key["forecast"]["bf_uplift"])
yc = w.copy()
yc.loc[BF] = base_bf
vals = yc.values
N = len(vals)
num = den = 0.0
for origin in range(30, N - 1):
    hmax = min(14, N - origin)
    f = vals[origin - 4:origin].mean()
    for k in range(1, hmax + 1):
        a = vals[origin + k - 1]
        num += abs(a - f)
        den += a
met = {m["model"]: m for m in key["forecast"]["metrics"]}
naive4 = [m for n, m in met.items() if n.startswith("Naif: son 4")][0]
chk("naif-4 modeli WAPE 1-14 hafta (%)", num / den * 100, naive4["WAPE_h1-14_%"], tol=5e-4)

vm = v.copy()
vm["m"] = vm["d"].dt.to_period("M")
mon = vm.groupby("m")["value"].sum()
y17 = mon.loc["2017-01":"2017-07"].sum()
y18 = mon.loc["2018-01":"2018-07"].sum()
chk("Ocak-Temmuz 2017 ciro (R$)", float(y17), key["forecast"]["ytd17"], tol=1e-9)
chk("Ocak-Temmuz 2018 ciro (R$)", float(y18), key["forecast"]["ytd18"], tol=1e-9)
chk("yıllık büyüme Ocak-Temmuz (%)", float((y18 / y17 - 1) * 100), key["forecast"]["yoy_pct"])
fw = key["forecast"]["forecast_weeks"]
tot = sum(r["tahmin_taban"] for r in fw)
chk("14 haftalık taban toplam (R$, yuvarlama payı ile)", float(tot), key["forecast"]["total_14w_base"], tol=1e-5)
print(f"  14 hafta %80 aralık (R$ mn): {tot * key['forecast']['total_ratio_q'][0] / 1e6:.2f} - "
      f"{tot * key['forecast']['total_ratio_q'][2] / 1e6:.2f} | medyan senaryo {tot * key['forecast']['total_ratio_q'][1] / 1e6:.2f}")

# ----------------------------------------------------------------- yönetici özeti için ek rakamlar
vv["first_day"] = vv["d"] == vv["fd"]
y2018 = vv[(vv["d"] >= pd.Timestamp("2018-01-01")) & (vv["d"] <= pd.Timestamp("2018-07-31"))]
share_first_2018 = float(y2018.loc[y2018["first_day"], "value"].sum() / y2018["value"].sum() * 100)
lat = vv[~vv["first_day"]]
rep_ids = F[F >= 2].index
post_first_spend = lat[lat["customer_unique_id"].isin(rep_ids)].groupby("customer_unique_id")["value"].sum()
fm_all = first.dt.to_period("M")
new_monthly = fm_all[(fm_all >= pd.Period("2018-01", "M")) & (fm_all <= pd.Period("2018-07", "M"))].groupby(level=0).size()
n_new_avg = float(fm_all[(fm_all >= pd.Period("2018-01", "M")) & (fm_all <= pd.Period("2018-07", "M"))].value_counts().mean())
mm_rev = key["forecast"]["monthly_mean_2018_mar_jul"]
v_rep = float(post_first_spend.mean())
delta_1pp = n_new_avg * 0.01 * v_rep
delta_x2 = n_new_avg * (key["churn"]["repeat_180_pct"] / 100) * v_rep
d = key["churn"]["drivers"]
n_deliv = [r for r in d if r["faktor"] == "Teslimat süresi"]
late21_share = [r for r in n_deliv if r["seviye"] == ">21 gün"][0]["n"] / sum(r["n"] for r in n_deliv) * 100
extras = {
    "revenue_share_first_day_orders_2018_jan_jul_pct": share_first_2018,
    "later_day_orders": int(len(lat)),
    "later_day_order_avg_value": float(lat["value"].mean()),
    "repeater_post_first_day_spend_avg": v_rep,
    "new_customers_per_month_2018_jan_jul": n_new_avg,
    "plus_1pp_repeat_monthly_revenue": float(delta_1pp),
    "plus_1pp_repeat_pct_of_monthly_revenue": float(delta_1pp / mm_rev * 100),
    "doubling_repeat_monthly_revenue": float(delta_x2),
    "doubling_repeat_pct_of_monthly_revenue": float(delta_x2 / mm_rev * 100),
    "eligible_first_orders_over_21d_delivery_pct": float(late21_share),
    "top_two_segments_revenue_share_pct": float(seg_main.loc[["Yeni - yüksek sepet", "Kayıp - yüksek değerli"], "ciro_payi_%"].sum()),
    "top_two_segments_customer_share_pct": float(seg_main.loc[["Yeni - yüksek sepet", "Kayıp - yüksek değerli"], "musteri_payi_%"].sum()),
    "yeni_segments_customers": int(seg_main.loc[["Yeni - yüksek sepet", "Yeni - standart"], "musteri"].sum()),
}
print("\n== Ek rakamlar ==")
for k, val in extras.items():
    print(f"  {k}: {val:,.2f}")

key["extras"] = extras
key["verification"] = {"checks": len(results), "passed": int(sum(results))}
json.dump(key, open(keyf, "w"), ensure_ascii=False, indent=2, default=float)
print(f"\nDoğrulama: {sum(results)}/{len(results)} kontrol tamam.")
sys.exit(0 if all(results) else 1)
