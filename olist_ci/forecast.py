"""Haftalık satış (ciro) tahmini.

* Seri: Pazartesi başlayan haftalık ciro, config.SERIES_START ... config.LAST_FULL_WEEK (85 hafta).
  20 Ağustos 2018 haftasından itibaren veri eksik olduğundan seri orada kesilir.
* Veri yeterliliği: yıllık mevsimsellik için en az iki tam yıl (≥104 hafta) gerekir; elimizde 85 hafta var.
  Bu yüzden mevsimsel model kurulmaz. Black Friday (Kasım 2017) tek bir olay olarak ayrılır: tahmin serisinde
  o hafta önceki iki haftanın ortalamasıyla değiştirilir, çarpan ayrıca raporlanır.
* Doğrulama: zaman sıralı, kayan başlangıçlı (rolling-origin) geriye dönük test. Her başlangıçta model yalnızca
  o haftaya kadarki veriyle kurulur ve sonraki 1-14 hafta tahmin edilir.
* Başlangıç (baseline) tahmini: son 4 haftanın ortalaması (naif).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config

MIN_WEEKS_FOR_SEASONALITY = 104


def weekly_series(orders: pd.DataFrame, start=config.SERIES_START, last_full=config.LAST_FULL_WEEK) -> pd.Series:
    o = orders[orders["purchase_date"] >= start]
    week = o["purchase_date"] - pd.to_timedelta(o["purchase_date"].dt.weekday, unit="D")
    w = o.groupby(week)["order_value"].sum()
    w = w[w.index <= last_full]
    return w.reindex(pd.date_range(start, last_full, freq="7D"), fill_value=0.0).rename("ciro")


def clean_event(y: pd.Series, event_week: pd.Timestamp):
    """Olay haftasını önceki iki haftanın ortalamasıyla değiştirir. Döndürür: (temiz_seri, çarpan, ham_değer)."""
    base = float(np.mean([y.loc[event_week - pd.Timedelta(days=14)], y.loc[event_week - pd.Timedelta(days=7)]]))
    raw = float(y.loc[event_week])
    yc = y.copy()
    yc.loc[event_week] = base
    return yc, raw / base, raw


# ------------------------------------------------------------------ modeller: f(geçmiş_dizi, ufuk) -> tahmin dizisi
def naive_mean(k: int):
    def f(hist, h):
        return np.repeat(np.mean(hist[-k:]), h)
    return f


def loglinear_trend(k: int):
    def f(hist, h):
        z = np.log(hist[-k:])
        t = np.arange(len(z))
        b, a = np.polyfit(t, z, 1)
        return np.exp(a + b * (len(z) + np.arange(h)))
    return f


def _holt_run(z, alpha, beta, phi):
    level = z[:4].mean()
    trend = (z[4:8].mean() - z[:4].mean()) / 4 if len(z) >= 8 else 0.0
    sse = 0.0
    for t in range(len(z)):
        sse += (z[t] - (level + phi * trend)) ** 2
        new = alpha * z[t] + (1 - alpha) * (level + phi * trend)
        trend = beta * (new - level) + (1 - beta) * phi * trend
        level = new
    return sse, level, trend


HOLT_GRID = [(a, b, p) for a in (0.1, 0.2, 0.3, 0.5, 0.7) for b in (0.05, 0.1, 0.2) for p in (0.8, 0.9, 0.95, 0.98)]


def damped_holt(hist, h):
    """Log ölçeğinde sönümlü Holt; parametreler küçük bir ızgarada eğitim içi hata ile seçilir."""
    z = np.log(hist)
    best = min(HOLT_GRID, key=lambda g: _holt_run(z, *g)[0])
    _, level, trend = _holt_run(z, *best)
    phi = best[2]
    steps = np.cumsum([phi ** i for i in range(1, h + 1)])
    return np.exp(level + steps * trend)


BASELINE = "Naif: son 4 hafta ortalaması"
MODELS = {
    BASELINE: naive_mean(4),
    "Naif: son 13 hafta ortalaması": naive_mean(13),
    "Log-doğrusal trend (son 26 hafta)": loglinear_trend(26),
    "Sönümlü Holt (log ölçeği)": damped_holt,
}


def backtest(y: pd.Series, models=None, horizon: int = config.FORECAST_HORIZON,
             min_train: int = config.MIN_TRAIN_WEEKS) -> pd.DataFrame:
    """Kayan başlangıçlı test. Her satır: model, başlangıç (eğitimdeki son hafta), ufuk h, gerçek, tahmin."""
    models = models or MODELS
    vals = y.values
    n = len(vals)
    rows = []
    for name, f in models.items():
        for origin in range(min_train, n - 1):
            hmax = min(horizon, n - origin)
            fc = f(vals[:origin], hmax)          # yalnızca geçmiş: vals[:origin]
            for k in range(1, hmax + 1):
                rows.append((name, y.index[origin - 1], k, vals[origin + k - 1], fc[k - 1]))
    bt = pd.DataFrame(rows, columns=["model", "baslangic", "h", "gercek", "tahmin"])
    bt["mutlak_hata"] = (bt["gercek"] - bt["tahmin"]).abs()
    bt["oran"] = bt["gercek"] / bt["tahmin"]
    return bt


def wape(d: pd.DataFrame) -> float:
    return float(d["mutlak_hata"].sum() / d["gercek"].sum() * 100)


def bias(d: pd.DataFrame) -> float:
    """+ : fazla tahmin, − : eksik tahmin (%)."""
    return float((d["tahmin"].sum() / d["gercek"].sum() - 1) * 100)


def metrics(bt: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for name, d in bt.groupby("model", sort=False):
        rows.append({"model": name, "baslangic_modeli": name == BASELINE,
                     "WAPE_h1-4_%": wape(d[d.h <= 4]), "WAPE_h5-14_%": wape(d[d.h >= 5]),
                     "WAPE_h1-14_%": wape(d), "yanlilik_h1-14_%": bias(d), "test_sayisi": len(d)})
    m = pd.DataFrame(rows).sort_values("WAPE_h1-14_%").reset_index(drop=True)
    base = m.loc[m["model"] == BASELINE, "WAPE_h1-14_%"].iloc[0]
    m["baslangica_gore_iyilesme_puan"] = base - m["WAPE_h1-14_%"]
    return m


def final_forecast(y: pd.Series, bt: pd.DataFrame, model: str, horizon: int = config.FORECAST_HORIZON,
                   event_uplift: float | None = None, event_week: pd.Timestamp | None = None):
    """Seçilen modelle ileriye tahmin; aralıklar modelin geriye dönük gerçek/tahmin oranlarından."""
    fc = MODELS[model](y.values, horizon)
    d = bt[bt.model == model]
    q = {lab: d.loc[m, "oran"].quantile([.1, .5, .9]).tolist()
         for lab, m in [("h1-4", d.h <= 4), ("h5-14", d.h >= 5)]}
    idx = pd.date_range(y.index[-1] + pd.Timedelta(days=7), periods=horizon, freq="7D")
    lo = [fc[i] * (q["h1-4"][0] if i < 4 else q["h5-14"][0]) for i in range(horizon)]
    hi = [fc[i] * (q["h1-4"][2] if i < 4 else q["h5-14"][2]) for i in range(horizon)]
    fdf = pd.DataFrame({"hafta_baslangic": idx, "tahmin_taban": fc, "alt_%10": lo, "ust_%90": hi})
    if event_uplift is not None and event_week is not None:
        fdf["olay_senaryosu"] = np.where(fdf["hafta_baslangic"] == event_week, fdf["tahmin_taban"] * event_uplift,
                                         fdf["tahmin_taban"])
    tot = d.groupby("baslangic").agg(n=("h", "size"), a=("gercek", "sum"), f=("tahmin", "sum"))
    tot = tot[tot["n"] == horizon]
    ratio = tot["a"] / tot["f"]
    total = {
        "toplam_taban": float(fdf["tahmin_taban"].sum()),
        "toplam_oran_q10_q50_q90": ratio.quantile([.1, .5, .9]).tolist() if len(ratio) >= 8 else [np.nan] * 3,
        "toplam_icin_baslangic_sayisi": int(len(ratio)),
        "haftalik_oran_ceyrekleri": q,
    }
    t = total["toplam_oran_q10_q50_q90"]
    total["toplam_alt_%10"] = total["toplam_taban"] * t[0]
    total["toplam_medyan"] = total["toplam_taban"] * t[1]
    total["toplam_ust_%90"] = total["toplam_taban"] * t[2]
    if "olay_senaryosu" in fdf:
        total["toplam_olay_senaryosu"] = float(fdf["olay_senaryosu"].sum())
    return fdf, total


def monthly_table(orders: pd.DataFrame, last_full_month=config.LAST_FULL_MONTH) -> pd.DataFrame:
    o = orders[orders["purchase_date"] >= "2017-01-01"]
    m = o.groupby("purchase_month").agg(siparis=("order_id", "size"), ciro=("order_value", "sum"))
    m["ort_siparis_degeri"] = m["ciro"] / m["siparis"]
    m["aylik_degisim_%"] = m["ciro"].pct_change() * 100
    m["tam_ay"] = m.index <= last_full_month
    m.index = m.index.astype(str)
    m.index.name = "ay"
    return m


def data_sufficiency(y: pd.Series) -> dict:
    return {"hafta_sayisi": int(len(y)), "mevsimsellik_icin_gereken_hafta": MIN_WEEKS_FOR_SEASONALITY,
            "mevsimsellik_tahmin_edilebilir": bool(len(y) >= MIN_WEEKS_FOR_SEASONALITY),
            "seri_baslangic": str(y.index[0].date()), "seri_bitis": str(y.index[-1].date())}
