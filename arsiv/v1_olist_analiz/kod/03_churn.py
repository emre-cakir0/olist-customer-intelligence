"""Adım 3 - Müşteri kaybı (churn).

Kullanım: python3 -I 03_churn.py <cikti_klasoru>

Tanım: İlk siparişin TESLİMATINDAN sonraki 180 gün içinde yeni bir günde sipariş vermeyen müşteri = kayıp.
(180 gün: tekrar alanların ~%76'sı 180 gün içinde dönüyor.)
Teslimattan önce ikinci alışverişi yapmış müşteriler analiz dışı bırakılır (özellikler henüz oluşmamış olur).
"""
import json
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

out = sys.argv[1]
SNAPSHOT = pd.Timestamp("2018-09-01")
W = 180
rng = np.random.default_rng(42)

o = pd.read_pickle(os.path.join(out, "orders.pkl"))
it = pd.read_pickle(os.path.join(out, "items.pkl"))
cust = pd.read_pickle(os.path.join(out, "customer_rfm.pkl"))
keyf = os.path.join(out, "key_numbers.json")
key = json.load(open(keyf))


def wilson(k, n, z=1.96):
    if n == 0:
        return (np.nan, np.nan)
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (c - h, c + h)


# ---------------------------------------------------------------- genel görünüm
lapsed180 = float((cust.R > 180).mean() * 100)
lapsed365 = float((cust.R > 365).mean() * 100)
never = float((cust.F == 1).mean() * 100)
print(f"Son alışverişi 180 günden eski müşteri payı : {lapsed180:.1f}%")
print(f"Son alışverişi 365 günden eski müşteri payı : {lapsed365:.1f}%")
print(f"Hiç tekrar alım yapmamış (F=1) müşteri payı : {never:.1f}%")

# ---------------------------------------------------------------- analiz popülasyonu
first = o.drop_duplicates("customer_unique_id").set_index("customer_unique_id").copy()
first["deliv_ts"] = first["purchase_ts"] + pd.to_timedelta(first["delivery_days"], unit="D")
first["deliv_date"] = first["deliv_ts"].dt.normalize()
d = first.join(cust[["first_date", "gap_days", "F", "R", "M", "segment"]])
d["second_date"] = d["first_date"] + pd.to_timedelta(d["gap_days"], unit="D")
n_all = len(d)
d = d[d["deliv_ts"].notna()]
n_deliv = len(d)
early = d["second_date"].notna() & (d["second_date"] <= d["deliv_date"])
n_early = int(early.sum())
d = d[~early].copy()
d["days_to_repeat"] = (d["second_date"] - d["deliv_date"]).dt.days
d["y"] = ((d["days_to_repeat"] > 0) & (d["days_to_repeat"] <= W)).astype(int)
d["window_closed"] = (d["deliv_date"] + pd.Timedelta(days=W)) <= SNAPSHOT
elig = d[(d["deliv_date"] >= pd.Timestamp("2017-01-01")) & d["window_closed"]].copy()
print(f"\nPopülasyon: {n_all:,d} müşteri -> teslim edilmiş ilk sipariş {n_deliv:,d} -> "
      f"teslimattan önce tekrar alan {n_early:,d} çıkarıldı -> 180g penceresi kapanmış {len(elig):,d}")
base = float(elig["y"].mean() * 100)
print(f"180 günde tekrar alım oranı: {base:.2f}%  (kayıp oranı {100-base:.2f}%)  pozitif: {int(elig['y'].sum()):,d}")

# ---------------------------------------------------------------- etken tabloları
cat_first = it.drop_duplicates("order_id").set_index("order_id")["category_en"]
elig["cat1"] = elig["order_id"].map(cat_first).fillna("unknown")


def add(rows, factor, labels, mask_series):
    for lab, m in mask_series:
        sub = elig[m]
        n, k = len(sub), int(sub["y"].sum())
        lo, hi = wilson(k, n)
        rows.append({"faktor": factor, "seviye": lab, "n": n, "tekrar_alim_%": k / n * 100 if n else np.nan,
                     "ci_alt_%": lo * 100, "ci_ust_%": hi * 100})


rows = []
rs = elig["review_score"].round()
add(rows, "Yorum puanı (ilk sipariş)", None,
    [(str(int(s)), rs == s) for s in [1, 2, 3, 4, 5]] + [("yorum yok", rs.isna())])
dl = elig["delay_days"]
add(rows, "Teslimat gecikmesi (tahmini tarihe göre)", None, [
    ("zamanında / erken", dl <= 0),
    ("1-7 gün gecikmiş", (dl > 0) & (dl <= 7)),
    (">7 gün gecikmiş", dl > 7),
])
dv = elig["delivery_days"]
add(rows, "Teslimat süresi", None, [
    ("≤7 gün", dv <= 7), ("8-14 gün", (dv > 7) & (dv <= 14)),
    ("15-21 gün", (dv > 14) & (dv <= 21)), (">21 gün", dv > 21),
])
q = elig["order_value"].quantile([.25, .5, .75]).tolist()
add(rows, "İlk sipariş tutarı (çeyrekler)", None, [
    (f"≤R${q[0]:.0f}", elig["order_value"] <= q[0]),
    (f"R${q[0]:.0f}-{q[1]:.0f}", (elig["order_value"] > q[0]) & (elig["order_value"] <= q[1])),
    (f"R${q[1]:.0f}-{q[2]:.0f}", (elig["order_value"] > q[1]) & (elig["order_value"] <= q[2])),
    (f">R${q[2]:.0f}", elig["order_value"] > q[2]),
])
add(rows, "Siparişteki kalem sayısı", None, [
    ("1", elig["n_items"] == 1), ("2", elig["n_items"] == 2), ("3+", elig["n_items"] >= 3)])
add(rows, "Ödeme yöntemi", None, [
    (p, elig["pay_type"] == p) for p in ["credit_card", "boleto", "voucher", "debit_card"]])
inst = elig["installments"]
add(rows, "Taksit", None, [("1", inst <= 1), ("2-5", (inst >= 2) & (inst <= 5)), ("6+", inst >= 6)])
top_states = elig["customer_state"].value_counts().head(5).index.tolist()
add(rows, "Eyalet", None,
    [(s, elig["customer_state"] == s) for s in top_states] + [("diğer", ~elig["customer_state"].isin(top_states))])
top_cats = elig["cat1"].value_counts().head(10).index.tolist()
add(rows, "İlk siparişin kategorisi (en büyük 10)", None, [(c, elig["cat1"] == c) for c in top_cats])
drv = pd.DataFrame(rows)
drv.round(2).to_csv(os.path.join(out, "churn_drivers.csv"), index=False, encoding="utf-8-sig")
pd.set_option("display.width", 200)
print("\n== 180 günde tekrar alım oranı: etkenler ==")
print(drv.round(2).to_string(index=False))

# ---------------------------------------------------------------- model
top_s6 = elig["customer_state"].value_counts().head(6).index.tolist()
top_c12 = elig["cat1"].value_counts().head(12).index.tolist()


def feats(df):
    X = pd.DataFrame(index=df.index)
    X["yorum_puani"] = df["review_score"].fillna(5)
    X["yorum_yok"] = df["review_score"].isna().astype(int)
    X["dusuk_yorum(<=2)"] = (df["review_score"] <= 2).astype(int)
    X["gecikme_gun"] = df["delay_days"].clip(-30, 30).fillna(0)
    X["gec_teslim"] = (df["delay_days"] > 0).astype(int)
    X["teslim_suresi_gun"] = df["delivery_days"].clip(0, 60)
    X["log_siparis_tutari"] = np.log1p(df["order_value"])
    fs = (df["freight_sum"] / (df["price_sum"] + df["freight_sum"])).clip(0, 1)
    X["kargo_payi"] = fs.fillna(fs.median())
    X["kalem_sayisi"] = df["n_items"].clip(upper=5)
    X["cok_kategori"] = (df["n_categories"] >= 2).astype(int)
    X["taksit"] = df["installments"].clip(upper=12).fillna(1)
    for p in ["boleto", "voucher", "debit_card"]:  # referans: kredi kartı
        X[f"odeme_{p}"] = (df["pay_type"] == p).astype(int)
    for s in top_s6:
        X[f"eyalet_{s}"] = (df["customer_state"] == s).astype(int)
    for c in top_c12:
        X[f"kat_{c}"] = (df["cat1"] == c).astype(int)
    return X


X = feats(elig)
y = elig["y"].values
cont = ["yorum_puani", "gecikme_gun", "teslim_suresi_gun", "log_siparis_tutari", "kargo_payi", "kalem_sayisi", "taksit"]
tr_mask = (elig["deliv_date"] <= pd.Timestamp("2017-10-31")).values
te_mask = ~tr_mask
print(f"\nEğitim: {tr_mask.sum():,d} müşteri ({y[tr_mask].sum()} pozitif) | Test: {te_mask.sum():,d} ({y[te_mask].sum()} pozitif)")
mu, sd = X.loc[tr_mask, cont].mean(), X.loc[tr_mask, cont].std().replace(0, 1)
Xs = X.copy()
Xs[cont] = (Xs[cont] - mu) / sd

lr = LogisticRegression(C=0.5, max_iter=2000)
lr.fit(Xs[tr_mask], y[tr_mask])
p_lr = lr.predict_proba(Xs[te_mask])[:, 1]
gb = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=150, l2_regularization=2.0,
                                    min_samples_leaf=100, random_state=0)
gb.fit(X[tr_mask], y[tr_mask])
p_gb = gb.predict_proba(X[te_mask])[:, 1]
yt = y[te_mask]


def auc_ci(yt, p, n=300):
    a = roc_auc_score(yt, p)
    bs = []
    idx = np.arange(len(yt))
    for _ in range(n):
        s = rng.choice(idx, len(idx))
        if yt[s].sum() in (0, len(s)):
            continue
        bs.append(roc_auc_score(yt[s], p[s]))
    return a, np.percentile(bs, 2.5), np.percentile(bs, 97.5)


a_lr = auc_ci(yt, p_lr)
a_gb = auc_ci(yt, p_gb)
print(f"\nTest AUC  lojistik regresyon: {a_lr[0]:.3f} (%95 GA {a_lr[1]:.3f}-{a_lr[2]:.3f})")
print(f"Test AUC  gradient boosting : {a_gb[0]:.3f} (%95 GA {a_gb[1]:.3f}-{a_gb[2]:.3f})")

# basit referans: yalnızca yorum puanı + gecikme
a_review = roc_auc_score(yt, X.loc[te_mask, "yorum_puani"])
print(f"Test AUC  yalnızca yorum puanı (tek değişken): {a_review:.3f}")

best_name, p_best = ("lojistik", p_lr) if a_lr[0] >= a_gb[0] else ("gradient boosting", p_gb)
order_idx = np.argsort(-p_best)
dec = np.array_split(order_idx, 10)
test_base = yt.mean()
lift_rows = []
for i, ix in enumerate(dec, 1):
    lift_rows.append({"desil": i, "n": len(ix), "tekrar_alim_%": yt[ix].mean() * 100,
                      "lift": yt[ix].mean() / test_base})
lift = pd.DataFrame(lift_rows)
top_dec_capture = float(yt[dec[0]].sum() / yt.sum() * 100)
top3_capture = float(sum(yt[ix].sum() for ix in dec[:3]) / yt.sum() * 100)
print(f"\nEn iyi model: {best_name}. Test tabanı: %{test_base*100:.2f}")
print(lift.round(2).to_string(index=False))
print(f"İlk desil tüm tekrar alanların %{top_dec_capture:.1f}'ini yakalıyor; ilk 3 desil %{top3_capture:.1f}'ini.")

coef = pd.Series(lr.coef_[0], index=Xs.columns)
orr = pd.DataFrame({"katsayi": coef, "odds_orani": np.exp(coef)}).sort_values("katsayi")
orr.round(3).to_csv(os.path.join(out, "churn_model_oranlari.csv"), encoding="utf-8-sig")
print("\nLojistik: en olumsuz / en olumlu 6 değişken (sürekli değişkenler 1 SS başına):")
print(pd.concat([orr.head(6), orr.tail(6)]).round(3).to_string())

# ---------------------------------------------------------------- tüm popülasyonda nihai model ve skorlar
Xs_all = X.copy()
mu_a, sd_a = X[cont].mean(), X[cont].std().replace(0, 1)
Xs_all[cont] = (Xs_all[cont] - mu_a) / sd_a
lr_final = LogisticRegression(C=0.5, max_iter=2000).fit(Xs_all, y)

f1 = d[(d["F"] == 1)].copy()
f1["cat1"] = f1["order_id"].map(cat_first).fillna("unknown")
Xf = feats(f1)
Xf_s = Xf.copy()
Xf_s[cont] = (Xf_s[cont] - mu_a) / sd_a
f1["tekrar_alim_olasiligi_180g"] = lr_final.predict_proba(Xf_s)[:, 1]
f1["pencere_acik"] = ~f1["window_closed"]
sc = f1[["segment", "R", "F", "M", "tekrar_alim_olasiligi_180g", "pencere_acik"]].reset_index()
sc.round(5).to_csv(os.path.join(out, "musteri_skorlari.csv"), index=False, encoding="utf-8-sig")
open_ = sc[sc.pencere_acik]
print(f"\nSkorlanan tek alımlı müşteri: {len(sc):,d} | penceresi açık (hâlâ kazanılabilir): {len(open_):,d}")
print(open_.groupby("segment")["tekrar_alim_olasiligi_180g"].agg(["size", "mean"]).round(4).to_string())

# ---------------------------------------------------------------- grafikler
fig, axes = plt.subplots(1, 3, figsize=(14, 4.6), sharey=True)
panels = [
    ("Teslimat süresi", "Siparişten teslimata geçen süre", None),
    ("Teslimat gecikmesi", "Teslimat (tahmini tarihe göre)", None),
    ("Yorum puanı", "İlk siparişin yorum puanı", "yorum yok"),
]
ymax = float(drv["ci_ust_%"][drv.faktor.str.startswith(("Teslimat", "Yorum"))].max()) + 0.55
for ax, (prefix, xl, skip) in zip(axes, panels):
    r = drv[drv.faktor.str.startswith(prefix)]
    if skip:
        r = r[r.seviye != skip]
    ax.bar(r.seviye, r["tekrar_alim_%"], color="#1f5f8b", width=0.62,
           yerr=[r["tekrar_alim_%"] - r["ci_alt_%"], r["ci_ust_%"] - r["tekrar_alim_%"]],
           capsize=3, error_kw={"lw": 1, "ecolor": "#444"})
    for x_, v, hi in zip(r.seviye, r["tekrar_alim_%"], r["ci_ust_%"]):
        ax.text(x_, hi + 0.07, f"{v:.1f}".replace(".", ","), ha="center", fontsize=9, fontweight="bold")
    ax.axhline(base, color="#c0392b", lw=1, ls="--")
    ax.set_xlabel(xl)
    ax.set_ylim(0, ymax)
    for s_ in ["top", "right"]:
        ax.spines[s_].set_visible(False)
axes[0].set_ylabel("180 günde tekrar alım (%)")
axes[0].set_title("Teslimat süresi", fontsize=10.5)
axes[1].set_title("Teslimat gecikmesi", fontsize=10.5)
axes[2].set_title("Yorum puanı", fontsize=10.5)
fig.suptitle(f"İlk siparişin tesliminden sonra 180 günde tekrar alım oranı (%95 güven aralığıyla; kırmızı çizgi = ortalama %{base:.1f})".replace(".", ","), fontsize=11)
fig.tight_layout()
fig.savefig(os.path.join(out, "fig_churn_drivers.png"), dpi=160)
plt.close(fig)

fig, ax = plt.subplots(figsize=(8, 4.2))
ax.bar(lift["desil"], lift["tekrar_alim_%"], color="#1f5f8b")
ax.axhline(test_base * 100, color="#c0392b", lw=1, ls="--")
for x_, v in zip(lift["desil"], lift["tekrar_alim_%"]):
    ax.text(x_, v + 0.06, f"{v:.1f}".replace(".", ","), ha="center", fontsize=8)
ax.set_xticks(range(1, 11))
ax.set_xlabel("Model skoru desili (1 = en yüksek tekrar alım olasılığı)")
ax.set_ylabel("Gerçekleşen tekrar alım (%)")
ax.set_title(f"Zaman bazlı test setinde model sıralaması (AUC {max(a_lr[0], a_gb[0]):.2f})".replace(".", ","), fontsize=10.5)
for s_ in ["top", "right"]:
    ax.spines[s_].set_visible(False)
fig.tight_layout()
fig.savefig(os.path.join(out, "fig_churn_model_lift.png"), dpi=160)
plt.close(fig)

key["churn"] = {
    "window_days": W,
    "lapsed_180_pct": lapsed180,
    "lapsed_365_pct": lapsed365,
    "never_returned_pct": never,
    "population": {"all": int(n_all), "delivered_first": int(n_deliv), "early_repeat_removed": n_early,
                   "eligible": int(len(elig)), "positives": int(elig["y"].sum())},
    "repeat_180_pct": base,
    "auc_logit": a_lr, "auc_gbm": a_gb, "auc_review_only": float(a_review),
    "best_model": best_name,
    "top_decile_capture_pct": top_dec_capture, "top3_deciles_capture_pct": top3_capture,
    "test_base_pct": float(test_base * 100),
    "lift": json.loads(lift.round(3).to_json(orient="records")),
    "drivers": json.loads(drv.round(3).to_json(orient="records", force_ascii=False)),
}
json.dump(key, open(keyf, "w"), ensure_ascii=False, indent=2, default=float)
print("\nkaydedildi.")
