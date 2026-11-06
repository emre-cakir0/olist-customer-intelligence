"""Adım 2 - Kohort analizi ve RFM segmentasyonu.

Kullanım: python3 -I 02_cohort_rfm.py <cikti_klasoru>
"""
import json
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

out = sys.argv[1]
SNAPSHOT = pd.Timestamp("2018-09-01")
LAST_MONTH = pd.Period("2018-08", "M")

o = pd.read_pickle(os.path.join(out, "orders.pkl"))
cust = pd.read_pickle(os.path.join(out, "customers.pkl"))
keyf = os.path.join(out, "key_numbers.json")
key = json.load(open(keyf)) if os.path.exists(keyf) else {}

# ============================ KOHORT ============================================
# Kohort = müşterinin ilk alışveriş ayı. Tekrar alım = ilk alışveriş gününden SONRAKİ bir günde sipariş.
# (Aynı gün verilen ek siparişler sepet bölünmesi sayılır, tekrar alım sayılmaz.)
coh = cust[(cust.first_month >= pd.Period("2017-01", "M")) & (cust.first_month < LAST_MONTH)].copy()
sizes = coh.groupby("first_month").size()

oo = o.merge(cust[["first_date", "first_month"]], left_on="customer_unique_id", right_index=True)
oo = oo[(oo.purchase_date > oo.first_date) & oo.first_month.isin(coh.first_month.unique())].copy()
oo["offset"] = (oo.purchase_month.astype(int) - oo.first_month.astype(int))
ret = (
    oo[oo.offset.between(1, 12)]
    .groupby(["first_month", "offset"])["customer_unique_id"].nunique()
    .unstack(fill_value=0)
    .reindex(index=sizes.index, columns=range(1, 13), fill_value=0)
)
retp = ret.div(sizes, axis=0) * 100
# gözlenemeyen hücreleri maskele (kohort ayı + k > son tam ay)
for cm in retp.index:
    for k in retp.columns:
        if (cm + k) > LAST_MONTH:
            retp.loc[cm, k] = np.nan
            ret.loc[cm, k] = np.nan

# ağırlıklı ortalama aylık tutunma (yalnızca gözlenen hücreler)
w = {}
for k in [1, 2, 3, 6, 12]:
    obs = ret[k].notna()
    w[k] = float(ret.loc[obs, k].sum() / sizes[obs].sum() * 100)
print("== Ağırlıklı aylık tutunma (kohort ayından k ay sonra, % ) ==")
for k, v in w.items():
    print(f"  k={k:>2d}: {v:.2f}%")

# N gün içinde 2. alışveriş (tam gözlenebilen kohortlar)
second = (
    o.merge(cust[["first_date"]], left_on="customer_unique_id", right_index=True)
    .query("purchase_date > first_date")
    .groupby("customer_unique_id")["purchase_date"].min()
)
cust["second_date"] = second
cust["gap_days"] = (cust["second_date"] - cust["first_date"]).dt.days
rep = {}
for n in [30, 90, 180, 365]:
    elig = cust[(cust.first_date + pd.Timedelta(days=n)) <= SNAPSHOT]
    elig = elig[elig.first_month >= pd.Period("2017-01", "M")]
    rep[n] = float((elig.gap_days <= n).mean() * 100)
print("\n== İlk alımdan sonraki N gün içinde tekrar alım oranı (tam gözlenen müşteriler) ==")
for n, v in rep.items():
    print(f"  {n:>3d} gün: {v:.2f}%")

g = cust["gap_days"].dropna()
gap_stats = {
    "repeaters": int(len(g)),
    "median": float(g.median()),
    "p25": float(g.quantile(.25)),
    "p75": float(g.quantile(.75)),
    "p90": float(g.quantile(.90)),
    "within_30": float((g <= 30).mean() * 100),
    "within_90": float((g <= 90).mean() * 100),
    "within_180": float((g <= 180).mean() * 100),
    "within_365": float((g <= 365).mean() * 100),
}
print("\n== Tekrar alanlarda 2. alışverişe kadar geçen gün ==")
for k, v in gap_stats.items():
    print(f"  {k:>10s}: {v:,.1f}")

# kohort tabloları
cohort_tbl = retp.copy()
cohort_tbl.insert(0, "kohort_buyuklugu", sizes)
cohort_tbl.index = cohort_tbl.index.astype(str)
cohort_tbl.round(2).to_csv(os.path.join(out, "cohort_retention.csv"), encoding="utf-8-sig")

per = []
for cm in sizes.index:
    sub = cust[cust.first_month == cm]
    row = {"kohort": str(cm), "musteri": len(sub)}
    for n in [90, 180]:
        full = (cm.end_time.normalize() + pd.Timedelta(days=n)) <= SNAPSHOT
        row[f"tekrar_{n}g_%"] = round(float((sub.gap_days <= n).mean() * 100), 2) if full else np.nan
    per.append(row)
per = pd.DataFrame(per)
per.to_csv(os.path.join(out, "cohort_repeat_rates.csv"), index=False, encoding="utf-8-sig")
print("\n== Kohort başına tekrar alım (90g / 180g) ==")
print(per.to_string(index=False))

# ısı haritası
fig, ax = plt.subplots(figsize=(11, 6.6))
data = retp.values
im = ax.imshow(data, cmap="YlGnBu", aspect="auto", vmin=0, vmax=1.0)
ax.set_xticks(range(12)); ax.set_xticklabels(range(1, 13))
ax.set_yticks(range(len(retp))); ax.set_yticklabels([f"{str(i)}  (n={sizes[i]:,d})".replace(",", ".") for i in retp.index], fontsize=8)
for i in range(data.shape[0]):
    for j in range(data.shape[1]):
        if not np.isnan(data[i, j]):
            ax.text(j, i, f"{data[i, j]:.2f}".replace(".", ","), ha="center", va="center", fontsize=7,
                    color="white" if data[i, j] > 0.6 else "#222")
ax.set_xlabel("İlk alışverişten sonraki ay")
ax.set_ylabel("Edinim kohortu (ilk alışveriş ayı)")
ax.set_title("Aylık tutunma: kohorttan o ay tekrar alışveriş yapanların payı (%)\n"
             "Her hücre 1'in altında; tutunma çok düşük", fontsize=11)
cb = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02); cb.set_label("%")
fig.tight_layout()
fig.savefig(os.path.join(out, "fig_cohort_retention.png"), dpi=160)
plt.close(fig)

# ============================ RFM ================================================
cust["F"] = cust["n_days"]
cust["R"] = cust["recency_days"]
cust["M"] = cust["monetary"]
r_code = pd.qcut(cust["R"], 5, labels=False, duplicates="drop")
m_code = pd.qcut(cust["M"], 5, labels=False, duplicates="drop")
cust["r_score"] = 5 - r_code           # 5 = en yakın dönem
cust["m_score"] = 1 + m_code           # 5 = en yüksek harcama
cust["f_class"] = np.where(cust["F"] >= 3, "3+", cust["F"].astype(str))

print("\n== Skor kesim noktaları ==")
print("Recency (gün) çeyreklik sınırları:", pd.qcut(cust["R"], 5, duplicates="drop").cat.categories.tolist())
print("Monetary (R$) sınırları          :", [round(x, 1) for x in cust["M"].quantile([.2, .4, .6, .8]).tolist()])

r, m, F = cust["r_score"], cust["m_score"], cust["F"]
conds = [
    (F >= 2) & (r >= 4),
    (F >= 2),
    (r >= 4) & (m >= 4),
    (r >= 4),
    (r == 3),
    (r <= 2) & (m >= 4),
]
names = ["Şampiyonlar", "Uyuyan sadıklar", "Yeni - yüksek sepet", "Yeni - standart", "Soğuyanlar",
         "Kayıp - yüksek değerli"]
cust["segment"] = np.select(conds, names, default="Kayıp - standart")

rv = o.groupby("customer_unique_id")["review_score"].mean()
cust["avg_review"] = rv
cust["aov"] = cust["monetary"] / cust["n_orders"]

order = ["Şampiyonlar", "Uyuyan sadıklar", "Yeni - yüksek sepet", "Yeni - standart", "Soğuyanlar",
         "Kayıp - yüksek değerli", "Kayıp - standart"]
seg = cust.groupby("segment").agg(
    musteri=("M", "size"),
    ciro=("M", "sum"),
    ort_harcama=("M", "mean"),
    ort_siparis_degeri=("aov", "mean"),
    ort_recency_gun=("R", "mean"),
    ort_alisveris_gunu=("F", "mean"),
    ort_yorum_puani=("avg_review", "mean"),
).reindex(order)
seg["musteri_payi_%"] = seg["musteri"] / seg["musteri"].sum() * 100
seg["ciro_payi_%"] = seg["ciro"] / seg["ciro"].sum() * 100
seg = seg[["musteri", "musteri_payi_%", "ciro", "ciro_payi_%", "ort_harcama", "ort_siparis_degeri",
           "ort_recency_gun", "ort_alisveris_gunu", "ort_yorum_puani"]]
pd.set_option("display.width", 220)
print("\n== RFM segmentleri ==")
print(seg.round(2).to_string())
seg.round(2).to_csv(os.path.join(out, "rfm_segments.csv"), encoding="utf-8-sig")

# gelir yoğunlaşması
srt = cust["M"].sort_values(ascending=False)
top20 = float(srt.head(int(len(srt) * .2)).sum() / srt.sum() * 100)
top10 = float(srt.head(int(len(srt) * .1)).sum() / srt.sum() * 100)
rep_rev = float(cust.loc[cust.F >= 2, "M"].sum() / cust["M"].sum() * 100)
print(f"\nEn yüksek harcayan %10 -> ciro payı {top10:.1f}% | %20 -> {top20:.1f}%")
print(f"≥2 alışveriş günü olan müşterilerin (%{(cust.F>=2).mean()*100:.2f}) ciro payı: {rep_rev:.1f}%")
print("Tek alımlı müşterilerin ort. harcaması: R$",
      round(cust.loc[cust.F == 1, "M"].mean(), 1), "| tekrar alanların ort. harcaması: R$",
      round(cust.loc[cust.F >= 2, "M"].mean(), 1))

cust.drop(columns=["second_date"]).to_pickle(os.path.join(out, "customer_rfm.pkl"))

# RFM grafiği: müşteri payı vs ciro payı
fig, ax = plt.subplots(figsize=(10, 5.2))
y = np.arange(len(order))[::-1]
ax.barh(y + 0.19, seg["musteri_payi_%"], height=0.36, color="#9db4c0", label="Müşteri payı (%)")
ax.barh(y - 0.19, seg["ciro_payi_%"], height=0.36, color="#1f5f8b", label="Ciro payı (%)")
for yi, a, b in zip(y, seg["musteri_payi_%"], seg["ciro_payi_%"]):
    ax.text(a + 0.4, yi + 0.19, f"{a:.1f}".replace(".", ","), va="center", fontsize=8)
    ax.text(b + 0.4, yi - 0.19, f"{b:.1f}".replace(".", ","), va="center", fontsize=8)
ax.set_yticks(y); ax.set_yticklabels(order)
ax.set_xlabel("%")
ax.set_title("RFM segmentleri: müşteri payı ve ciro payı")
ax.legend(frameon=False, loc="upper right")
for s in ["top", "right"]:
    ax.spines[s].set_visible(False)
fig.tight_layout()
fig.savefig(os.path.join(out, "fig_rfm_segments.png"), dpi=160)
plt.close(fig)

key["cohort"] = {
    "weighted_retention_pct": {str(k): v for k, v in w.items()},
    "repeat_within_days_pct": {str(k): v for k, v in rep.items()},
    "gap_stats": gap_stats,
    "n_cohorts": int(len(sizes)),
    "cohort_size_min": int(sizes.min()),
    "cohort_size_max": int(sizes.max()),
}
key["rfm"] = {
    "segments": json.loads(seg.round(4).reset_index().to_json(orient="records", force_ascii=False)),
    "top10_rev_share": top10,
    "top20_rev_share": top20,
    "repeater_rev_share": rep_rev,
    "repeater_customer_share": float((cust.F >= 2).mean() * 100),
}
json.dump(key, open(keyf, "w"), ensure_ascii=False, indent=2)
print("\nkaydedildi.")
