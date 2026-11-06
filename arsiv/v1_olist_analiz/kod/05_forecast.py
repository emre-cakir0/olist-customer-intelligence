"""Adım 5 - Basit satış tahmini (haftalık ciro).

Kullanım: python3 -I 05_forecast.py <cikti_klasoru>

Yalnızca 20 tam ay veri olduğundan yıllık mevsimsellik güvenilir şekilde tahmin edilemez.
Bu yüzden:
  * Haftalık seri kullanılır (2017-01-02 ... 2018-08-13, 85 hafta). 20 Ağustos haftasından itibaren veri eksiktir.
  * Black Friday haftası olay olarak ayrılır; seri temizlenir, çarpan ayrıca raporlanır.
  * Modeller kayan başlangıçlı (rolling-origin) geriye dönük testle karşılaştırılır.
statsmodels kurulamadığı için sönümlü Holt modeli numpy ile elle yazılmıştır.
"""
import json
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

out = sys.argv[1]
H = 14
MIN_TRAIN = 30
BF_WEEK = pd.Timestamp("2017-11-20")   # Black Friday 24.11.2017 bu haftanın cuması

o = pd.read_pickle(os.path.join(out, "orders.pkl"))
keyf = os.path.join(out, "key_numbers.json")
key = json.load(open(keyf))

# ----------------------------------------------------------------- seri
o = o[o["purchase_date"] >= "2017-01-02"].copy()
o["week"] = o["purchase_date"] - pd.to_timedelta(o["purchase_date"].dt.weekday, unit="D")
w = o.groupby("week")["order_value"].sum()
last_full = pd.Timestamp("2018-08-13")           # 20 Ağustos haftası ve sonrası eksik: günlük sipariş ~250'den ~70'e düşüyor (veri kesintisi)
w = w[w.index <= last_full]
w = w.reindex(pd.date_range(w.index.min(), last_full, freq="7D"), fill_value=0.0)
print(f"Haftalık seri: {len(w)} hafta, {w.index.min().date()} -> {w.index.max().date()}")
print("\nBlack Friday çevresi (R$ bin):")
print((w.loc["2017-10-30":"2017-12-18"] / 1000).round(0).to_string())

# temizlenmiş seri: BF haftasını önceki iki haftanın ortalamasıyla değiştir
y_raw = w.copy()
y = w.copy()
bf_prev, bf_next = BF_WEEK - pd.Timedelta(days=14), BF_WEEK + pd.Timedelta(days=14)
bf_base = float(np.mean([y_raw.loc[BF_WEEK - pd.Timedelta(days=14)], y_raw.loc[BF_WEEK - pd.Timedelta(days=7)]]))
bf_uplift = float(y_raw.loc[BF_WEEK] / bf_base)       # BF haftası / önceki iki haftanın ortalaması
y.loc[BF_WEEK] = bf_base
print(f"\nBlack Friday haftası: R${y_raw.loc[BF_WEEK]/1000:,.0f} bin | önceki iki hafta ortalamasının {bf_uplift:.2f} katı")
ly = np.log(y.values)

# ----------------------------------------------------------------- modeller
def f_naive(k):
    def f(hist, h):
        return np.repeat(np.mean(hist[-k:]), h)
    return f


def f_loglin(k):
    def f(hist, h):
        z = np.log(hist[-k:])
        t = np.arange(len(z))
        b, a = np.polyfit(t, z, 1)
        return np.exp(a + b * (len(z) + np.arange(h)))
    return f


def holt_run(z, alpha, beta, phi):
    l = z[:4].mean()
    b = (z[4:8].mean() - z[:4].mean()) / 4 if len(z) >= 8 else 0.0
    sse = 0.0
    for t in range(len(z)):
        pred = l + phi * b
        sse += (z[t] - pred) ** 2
        l_new = alpha * z[t] + (1 - alpha) * (l + phi * b)
        b = beta * (l_new - l) + (1 - beta) * phi * b
        l = l_new
    return sse, l, b


GRID = [(a, b_, p) for a in (0.1, 0.2, 0.3, 0.5, 0.7) for b_ in (0.05, 0.1, 0.2) for p in (0.8, 0.9, 0.95, 0.98)]


def f_holt(hist, h):
    z = np.log(hist)
    best = min(GRID, key=lambda g: holt_run(z, *g)[0])
    _, l, b = holt_run(z, *best)
    phi = best[2]
    steps = np.array([sum(phi ** i for i in range(1, k + 1)) for k in range(1, h + 1)])
    return np.exp(l + steps * b)


MODELS = {
    "Naif: son 4 hafta ortalaması": f_naive(4),
    "Naif: son 13 hafta ortalaması": f_naive(13),
    "Log-doğrusal trend (son 26 hafta)": f_loglin(26),
    "Sönümlü Holt (log ölçeği)": f_holt,
}

# ----------------------------------------------------------------- geriye dönük test
vals = y.values
N = len(vals)
bt = []
for name, f in MODELS.items():
    for origin in range(MIN_TRAIN, N - 1):               # origin = eğitimdeki son indeks + 1
        hmax = min(H, N - origin)
        fc = f(vals[:origin], hmax)
        for k in range(1, hmax + 1):
            bt.append({"model": name, "origin": y.index[origin - 1], "h": k,
                       "actual": vals[origin + k - 1], "fc": fc[k - 1]})
bt = pd.DataFrame(bt)
bt["abs_err"] = (bt.actual - bt.fc).abs()
bt["ratio"] = bt.actual / bt.fc


def wape(d):
    return d.abs_err.sum() / d.actual.sum() * 100


def bias(d):
    return (d.fc.sum() / d.actual.sum() - 1) * 100


rows = []
for name in MODELS:
    d = bt[bt.model == name]
    rows.append({
        "model": name,
        "WAPE_h1-4_%": wape(d[d.h <= 4]),
        "WAPE_h5-14_%": wape(d[d.h >= 5]),
        "WAPE_h1-14_%": wape(d),
        "yanlilik_h1-14_%": bias(d),
        "test_sayisi": len(d),
    })
met = pd.DataFrame(rows).sort_values("WAPE_h1-14_%")
met.round(2).to_csv(os.path.join(out, "tahmin_geriye_donuk_test.csv"), index=False, encoding="utf-8-sig")
pd.set_option("display.width", 200)
print("\n== Geriye dönük test (kayan başlangıç, BF temizlenmiş seri) ==")
print(met.round(2).to_string(index=False))
best = met.iloc[0]["model"]
print("\nEn iyi model:", best)

# ----------------------------------------------------------------- nihai tahmin + aralık
f_best = MODELS[best]
fc = f_best(vals, H)
d = bt[bt.model == best]
q = {}
for lab, mask in [("h1-4", d.h <= 4), ("h5-14", d.h >= 5)]:
    r = d.loc[mask, "ratio"]
    q[lab] = (float(r.quantile(.10)), float(r.quantile(.50)), float(r.quantile(.90)))
print("\nOran (gerçek/tahmin) 10-50-90. yüzdelikler:", {k: tuple(round(x, 3) for x in v) for k, v in q.items()})
fut_idx = pd.date_range(last_full + pd.Timedelta(days=7), periods=H, freq="7D")
lo = np.array([fc[i] * (q["h1-4"][0] if i < 4 else q["h5-14"][0]) for i in range(H)])
hi = np.array([fc[i] * (q["h1-4"][2] if i < 4 else q["h5-14"][2]) for i in range(H)])
fdf = pd.DataFrame({"hafta_baslangic": fut_idx, "tahmin_taban": fc, "alt_%10": lo, "ust_%90": hi})
# Black Friday 2018: 23.11.2018 -> 19.11.2018 haftası
bf18 = pd.Timestamp("2018-11-19")
fdf["black_friday_senaryosu"] = np.where(fdf.hafta_baslangic == bf18, fdf.tahmin_taban * bf_uplift, fdf.tahmin_taban)
fdf.assign(**{c: fdf[c].round(0) for c in fdf.columns if c != "hafta_baslangic"}).to_csv(os.path.join(out, "tahmin_14_hafta.csv"), index=False, encoding="utf-8-sig")
print("\n== 14 haftalık tahmin (R$ bin) ==")
print((fdf.set_index("hafta_baslangic") / 1000).round(0).to_string())

tot_base = float(fdf.tahmin_taban.sum())
# toplam için aralık: 14 hafta ileriye tam bakan başlangıçlardaki toplam oranı
d13 = bt[(bt.model == best)]
tot = d13.groupby("origin").agg(n=("h", "size"), a=("actual", "sum"), f=("fc", "sum"))
tot = tot[tot.n == H]
tr = (tot.a / tot.f)
tot_q = (float(tr.quantile(.10)), float(tr.quantile(.50)), float(tr.quantile(.90))) if len(tr) >= 8 else (np.nan,) * 3
print(f"\n14 haftalık toplam taban tahmin: R${tot_base/1e6:.2f} milyon | 14 haftalık tam başlangıç sayısı: {len(tr)} "
      f"| oran q10/q50/q90: {tuple(round(x, 3) for x in tot_q)}")
tot_bf = float(fdf.black_friday_senaryosu.sum())
print(f"Black Friday senaryosuyla toplam: R${tot_bf/1e6:.2f} milyon (+R${(tot_bf-tot_base)/1e3:,.0f} bin)")

# ----------------------------------------------------------------- aylık bağlam
o2 = pd.read_pickle(os.path.join(out, "orders.pkl"))
m = o2[o2.purchase_date >= "2017-01-01"].groupby("purchase_month").agg(
    siparis=("order_id", "size"), ciro=("order_value", "sum"))
m["ort_siparis_degeri"] = m.ciro / m.siparis
m["aylik_buyume_%"] = m.ciro.pct_change() * 100
m.index = m.index.astype(str)
m.round(2).to_csv(os.path.join(out, "aylik_ciro.csv"), encoding="utf-8-sig")
print("\n== Aylık ciro (R$ bin) ==")
print((m[["siparis", "ciro"]].assign(ciro=lambda x: (x.ciro / 1000).round(0))).T.to_string())
ytd17 = float(m.loc["2017-01":"2017-07", "ciro"].sum())
ytd18 = float(m.loc["2018-01":"2018-07", "ciro"].sum())
yoy = (ytd18 / ytd17 - 1) * 100
h1 = float(m.loc["2018-03":"2018-07", "ciro"].mean())
print(f"\nOcak-Temmuz ciro: 2017 R${ytd17/1e6:.2f} mn -> 2018 R${ytd18/1e6:.2f} mn  ({yoy:+.0f}%)")
print(f"2018 Mart-Temmuz ortalama aylık ciro: R${h1/1e3:,.0f} bin | Ağustos 2018 (eksik ay): R${m.loc['2018-08','ciro']/1e3:,.0f} bin")
last8 = y_raw.iloc[-8:].mean()
print(f"son 8 haftanın ortalama haftalık cirosu: R${last8/1e3:,.0f} bin | tahmin ortalaması: R${fdf.tahmin_taban.mean()/1e3:,.0f} bin")

# ----------------------------------------------------------------- grafikler
fig, axes = plt.subplots(1, 2, figsize=(14, 4.9), gridspec_kw={"width_ratios": [2.3, 1]})
ax = axes[0]
ax.plot(y_raw.index, y_raw.values / 1000, color="#1f5f8b", lw=1.6, label="Gerçekleşen haftalık ciro")
ax.scatter([BF_WEEK], [y_raw.loc[BF_WEEK] / 1000], color="#c0392b", zorder=3, s=22)
ax.annotate(f"Black Friday haftası\n({bf_uplift:.1f}× önceki iki hafta)".replace(".", ","),
            xy=(BF_WEEK, y_raw.loc[BF_WEEK] / 1000), xytext=(BF_WEEK - pd.Timedelta(days=125), y_raw.loc[BF_WEEK] / 1000 * 0.93),
            fontsize=8, color="#c0392b", arrowprops={"arrowstyle": "-", "color": "#c0392b", "lw": 0.8})
ax.fill_between(fdf.hafta_baslangic, fdf["alt_%10"] / 1000, fdf["ust_%90"] / 1000, color="#f39c12", alpha=0.22,
                label="%80 aralık (geriye dönük testteki hatalara göre)")
ax.plot(np.r_[y_raw.index[-1], fdf.hafta_baslangic], np.r_[y_raw.values[-1] / 1000, fdf.tahmin_taban / 1000],
        color="#e67e22", lw=1.8, ls="--", label="Taban tahmin (olay etkisi hariç)")
ax.scatter(fdf.loc[fdf.hafta_baslangic == bf18, "hafta_baslangic"],
           fdf.loc[fdf.hafta_baslangic == bf18, "black_friday_senaryosu"] / 1000, marker="^", color="#c0392b", s=34,
           zorder=3, label="Black Friday 2018 senaryosu")
ax.axvline(last_full + pd.Timedelta(days=3), color="#888", lw=0.8, ls=":")
ax.set_ylabel("R$ bin / hafta")
import matplotlib.ticker as mticker
TR_AY = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]
ax.xaxis.set_major_formatter(mticker.FuncFormatter(
    lambda v, _: (lambda d: f"{TR_AY[d.month - 1]} {d:%y}")(mdates.num2date(v))))
ax.set_title("Haftalık ciro ve sonraki 14 hafta tahmini", fontsize=10.5)
ax.legend(frameon=False, fontsize=8, loc="upper left")
for s_ in ["top", "right"]:
    ax.spines[s_].set_visible(False)

ax = axes[1]
mm = met.iloc[::-1]
colors = ["#1f5f8b" if n == best else "#9db4c0" for n in mm.model]
ax.barh(mm.model, mm["WAPE_h1-14_%"], color=colors)
for y_, v in enumerate(mm["WAPE_h1-14_%"]):
    ax.text(v + 0.3, y_, f"%{v:.1f}".replace(".", ","), va="center", fontsize=8)
ax.set_xlabel("WAPE (%), 1-14 hafta ileri, geriye dönük test")
ax.set_title("Model karşılaştırması (düşük = iyi)", fontsize=10.5)
ax.set_xlim(0, mm["WAPE_h1-14_%"].max() * 1.2)
for s_ in ["top", "right"]:
    ax.spines[s_].set_visible(False)
fig.tight_layout()
fig.savefig(os.path.join(out, "fig_tahmin.png"), dpi=160)
plt.close(fig)

key["forecast"] = {
    "weeks": int(len(y)), "last_full_week": str(last_full.date()), "horizon": H, "best_model": best,
    "metrics": json.loads(met.round(2).to_json(orient="records", force_ascii=False)),
    "bf_week_revenue": float(y_raw.loc[BF_WEEK]), "bf_uplift": bf_uplift,
    "ratio_quantiles": q, "total_ratio_q": list(tot_q), "n_total_origins": int(len(tr)),
    "total_14w_base": tot_base, "total_14w_with_bf": tot_bf,
    "weekly_mean_last8": float(last8), "weekly_mean_forecast": float(fdf.tahmin_taban.mean()),
    "ytd17": ytd17, "ytd18": ytd18, "yoy_pct": yoy,
    "monthly_mean_2018_mar_jul": h1, "aug18": float(m.loc["2018-08", "ciro"]),
    "forecast_weeks": json.loads(fdf.assign(**{c: fdf[c].round(0) for c in fdf.columns if c != "hafta_baslangic"}).assign(hafta_baslangic=fdf.hafta_baslangic.dt.strftime("%Y-%m-%d")).to_json(orient="records")),
}
json.dump(key, open(keyf, "w"), ensure_ascii=False, indent=2, default=float)
print("\nkaydedildi.")
