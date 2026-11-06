"""Grafikler (PNG). Her fonksiyon bir dosya yazar ve yolunu döndürür."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker as mticker  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

BLUE, GREY, RED, ORANGE = "#1f5f8b", "#9db4c0", "#c0392b", "#e67e22"
TR_MONTHS = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]


def tr(x: float, nd: int = 1) -> str:
    """Türkçe ondalık biçim: 1234.5 -> '1.234,5'."""
    s = f"{x:,.{nd}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def _clean(ax):
    for s in ["top", "right"]:
        ax.spines[s].set_visible(False)


def _save(fig, path: Path) -> Path:
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path


def cohort_heatmap(pct: pd.DataFrame, sizes: pd.Series, path: Path) -> Path:
    fig, ax = plt.subplots(figsize=(11, 6.6))
    data = pct.values.astype(float)
    vmax = max(1.0, float(np.nanmax(data)) if np.isfinite(data).any() else 1.0)
    im = ax.imshow(data, cmap="YlGnBu", aspect="auto", vmin=0, vmax=vmax)
    ax.set_xticks(range(data.shape[1]))
    ax.set_xticklabels(pct.columns)
    ax.set_yticks(range(len(pct)))
    ax.set_yticklabels([f"{i}  (n={tr(sizes[i], 0)})" for i in pct.index], fontsize=8)
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            if not np.isnan(data[i, j]):
                ax.text(j, i, tr(data[i, j], 2), ha="center", va="center", fontsize=7,
                        color="white" if data[i, j] > 0.6 * vmax else "#222")
    ax.set_xlabel("İlk siparişten sonraki ay")
    ax.set_ylabel("Kohort (ilk sipariş ayı)")
    ax.set_title(f"Aylık tutunma: kohorttan o ay yeniden alışveriş yapanların payı (%)\n"
                 f"En yüksek hücre %{tr(np.nanmax(data), 2)}; boş hücreler henüz gözlenmedi", fontsize=11)
    cb = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cb.set_label("%")
    return _save(fig, path)


def rfm_segments(seg: pd.DataFrame, path: Path) -> Path:
    fig, ax = plt.subplots(figsize=(10, 5.2))
    y = np.arange(len(seg))[::-1]
    ax.barh(y + 0.19, seg["musteri_payi_%"], height=0.36, color=GREY, label="Müşteri payı (%)")
    ax.barh(y - 0.19, seg["ciro_payi_%"], height=0.36, color=BLUE, label="Ciro payı (%)")
    for yi, a, b in zip(y, seg["musteri_payi_%"], seg["ciro_payi_%"]):
        ax.text(a + 0.4, yi + 0.19, tr(a), va="center", fontsize=8)
        ax.text(b + 0.4, yi - 0.19, tr(b), va="center", fontsize=8)
    ax.set_yticks(y)
    ax.set_yticklabels(seg.index)
    ax.set_xlabel("%")
    ax.set_title("RFM segmentleri: müşteri payı ve ciro payı")
    ax.legend(frameon=False, loc="upper right")
    _clean(ax)
    return _save(fig, path)


def churn_drivers(drv: pd.DataFrame, base: float, window: int, path: Path) -> Path:
    panels = [("Teslimat süresi", "Siparişten teslimata geçen süre", None),
              ("Teslimat gecikmesi", "Teslimat (tahmini tarihe göre)", None),
              ("Yorum puanı", "İlk siparişin yorum puanı", "yorum yok")]
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.6), sharey=True)
    sub = drv[drv["faktor"].isin([p[0] for p in panels])]
    ymax = float(sub["ga_ust_%"].max()) + 0.55
    for ax, (fac, xl, skip) in zip(axes, panels):
        r = drv[drv["faktor"] == fac]
        if skip:
            r = r[r["seviye"] != skip]
        ax.bar(r["seviye"], r["tekrar_alim_%"], color=BLUE, width=0.62,
               yerr=[r["tekrar_alim_%"] - r["ga_alt_%"], r["ga_ust_%"] - r["tekrar_alim_%"]],
               capsize=3, error_kw={"lw": 1, "ecolor": "#444"})
        for x_, v, hi in zip(r["seviye"], r["tekrar_alim_%"], r["ga_ust_%"]):
            ax.text(x_, hi + 0.07, tr(v), ha="center", fontsize=9, fontweight="bold")
        ax.axhline(base, color=RED, lw=1, ls="--")
        ax.set_xlabel(xl)
        ax.set_ylim(0, ymax)
        ax.set_title(fac, fontsize=10.5)
        _clean(ax)
    axes[0].set_ylabel(f"{window} günde tekrar alım (%)")
    fig.suptitle(f"İlk siparişin tesliminden sonra {window} günde tekrar alım (%95 güven aralığıyla; "
                 f"kırmızı çizgi = ortalama %{tr(base)})", fontsize=11)
    return _save(fig, path)


def churn_threshold_compare(per_window: dict[int, pd.DataFrame], path: Path) -> Path:
    """Teslimat süresi gruplarında tekrar alım oranı, 180 ve 365 günlük eşiklerle yan yana."""
    fig, ax = plt.subplots(figsize=(9, 4.4))
    windows = sorted(per_window)
    width = 0.8 / len(windows)
    colors = [BLUE, ORANGE, GREY]
    labels = None
    for i, w in enumerate(windows):
        r = per_window[w]
        r = r[r["faktor"] == "Teslimat süresi"]
        labels = list(r["seviye"])
        x = np.arange(len(r)) + (i - (len(windows) - 1) / 2) * width
        ax.bar(x, r["tekrar_alim_%"], width=width * 0.95, color=colors[i % 3], label=f"{w} gün",
               yerr=[r["tekrar_alim_%"] - r["ga_alt_%"], r["ga_ust_%"] - r["tekrar_alim_%"]],
               capsize=2, error_kw={"lw": 0.8, "ecolor": "#444"})
        for xi, v, hi in zip(x, r["tekrar_alim_%"], r["ga_ust_%"]):
            ax.text(xi, hi + 0.06, tr(v), ha="center", fontsize=8)
    ax.set_xticks(np.arange(len(labels)))
    ax.set_xticklabels(labels)
    ax.set_xlabel("Siparişten teslimata geçen süre")
    ax.set_ylabel("Tekrar alım (%)")
    ax.set_title("Eşik seçimi: teslimat süresine göre geri dönüş oranı (180 ve 365 gün)", fontsize=10.5)
    ax.legend(frameon=False, title="Pencere")
    _clean(ax)
    return _save(fig, path)


def churn_model_lift(lift: pd.DataFrame, model: dict, path: Path) -> Path:
    fig, ax = plt.subplots(figsize=(8, 4.2))
    ax.bar(lift["desil"], lift["tekrar_alim_%"], color=BLUE)
    ax.axhline(model["test_taban_%"], color=RED, lw=1, ls="--")
    for x_, v in zip(lift["desil"], lift["tekrar_alim_%"]):
        ax.text(x_, v + 0.06, tr(v), ha="center", fontsize=8)
    ax.set_xticks(range(1, 11))
    ax.set_xlabel("Model skoru desili (1 = en yüksek tahmini geri dönüş olasılığı)")
    ax.set_ylabel("Gerçekleşen tekrar alım (%)")
    ax.set_title(f"Zaman sıralı test: lojistik model AUC {tr(model['auc_lojistik'], 2)}, "
                 f"başlangıç kuralı AUC {tr(model['auc_baslangic_teslimat_kurali'], 2)} (zayıf ayrım)", fontsize=10)
    _clean(ax)
    return _save(fig, path)


def basket_pairs(pairs: pd.DataFrame, n_orders: int, path: Path, top: int = 10) -> Path:
    t = pairs.head(top).iloc[::-1]
    labels = [f"{a} + {b}" for a, b in zip(t["kategori_A"], t["kategori_B"])]
    fig, ax = plt.subplots(figsize=(10, 5.2))
    ax.barh(labels, t["birlikte_siparis"], color=[GREY if f else BLUE for f in t["dusuk_orneklem"]])
    for y_, n_, l_ in zip(range(len(t)), t["birlikte_siparis"], t["lift_cok_kategorili"]):
        ax.text(n_ + 0.8, y_, f"{n_}  (lift {tr(l_)})", va="center", fontsize=8)
    ax.set_xlabel(f"Birlikte alındığı sipariş sayısı ({tr(n_orders, 0)} sipariş içinde)")
    ax.set_xlim(0, t["birlikte_siparis"].max() * 1.25)
    ax.set_title("En sık birlikte alınan kategori çiftleri\n(lift: çok kategorili sepetlere göre; "
                 "gri = 30'dan az sipariş, düşük örneklem)", fontsize=10)
    _clean(ax)
    return _save(fig, path)


def forecast(y_raw: pd.Series, fdf: pd.DataFrame, met: pd.DataFrame, best: str, bf_week, bf_uplift: float,
             last_full, path: Path, base_fdf: pd.DataFrame | None = None) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(14, 4.9), gridspec_kw={"width_ratios": [2.3, 1]})
    ax = axes[0]
    ax.plot(y_raw.index, y_raw.values / 1000, color=BLUE, lw=1.6, label="Gerçekleşen haftalık ciro")
    ax.scatter([bf_week], [y_raw.loc[bf_week] / 1000], color=RED, zorder=3, s=22)
    ax.annotate(f"Black Friday haftası\n({tr(bf_uplift)}× önceki iki hafta)",
                xy=(bf_week, y_raw.loc[bf_week] / 1000),
                xytext=(bf_week - pd.Timedelta(days=125), y_raw.loc[bf_week] / 1000 * 0.93),
                fontsize=8, color=RED, arrowprops={"arrowstyle": "-", "color": RED, "lw": 0.8})
    ax.fill_between(fdf["hafta_baslangic"], fdf["alt_%10"] / 1000, fdf["ust_%90"] / 1000, color="#f39c12",
                    alpha=0.22, label="%80 aralık (geriye dönük testteki hatalara göre)")
    ax.plot(np.r_[y_raw.index[-1], fdf["hafta_baslangic"]], np.r_[y_raw.values[-1] / 1000,
            fdf["tahmin_taban"] / 1000], color=ORANGE, lw=1.8, ls="--", label="Taban tahmin (olay etkisi hariç)")
    if base_fdf is not None:
        ax.plot(base_fdf["hafta_baslangic"], base_fdf["tahmin_taban"] / 1000, color="#555", lw=1.3, ls=":",
                label="Başlangıç tahmini (son 4 hafta ortalaması)")
    if "olay_senaryosu" in fdf:
        ev = fdf[fdf["olay_senaryosu"] != fdf["tahmin_taban"]]
        ax.scatter(ev["hafta_baslangic"], ev["olay_senaryosu"] / 1000, marker="^", color=RED, s=34, zorder=3,
                   label="Black Friday 2018 senaryosu")
    ax.axvline(last_full + pd.Timedelta(days=3), color="#888", lw=0.8, ls=":")
    ax.set_ylabel("R$ bin / hafta")
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(
        lambda v, _: (lambda d: f"{TR_MONTHS[d.month - 1]} {d:%y}")(mdates.num2date(v))))
    ax.set_title("Haftalık ciro ve sonraki 14 hafta tahmini", fontsize=10.5)
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    _clean(ax)
    ax = axes[1]
    mm = met.iloc[::-1]
    colors = [BLUE if n == best else GREY for n in mm["model"]]
    ax.barh(mm["model"], mm["WAPE_h1-14_%"], color=colors)
    for y_, (v, b) in enumerate(zip(mm["WAPE_h1-14_%"], mm["baslangic_modeli"])):
        ax.text(v + 0.3, y_, f"%{tr(v)}" + ("  (başlangıç)" if b else ""), va="center", fontsize=8)
    ax.set_xlabel("WAPE (%), 1-14 hafta ileri, geriye dönük test")
    ax.set_title("Model karşılaştırması (düşük = iyi)", fontsize=10.5)
    ax.set_xlim(0, mm["WAPE_h1-14_%"].max() * 1.3)
    _clean(ax)
    return _save(fig, path)
