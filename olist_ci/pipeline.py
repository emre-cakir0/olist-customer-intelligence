"""Tüm hattı çalıştırır: veri -> analizler -> tablolar, grafikler, sonuclar.json, yönetici özeti."""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from . import basket, churn, cohort, config, data, forecast, plots, report, rfm


def _csv(df: pd.DataFrame, path: Path, index: bool = True) -> None:
    df.round(4).to_csv(path, index=index, encoding="utf-8-sig")


def _jsonable(x):
    if isinstance(x, dict):
        return {str(k): _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating, float)):
        return None if not np.isfinite(x) else round(float(x), 6)
    if isinstance(x, (np.bool_,)):
        return bool(x)
    if isinstance(x, (pd.Timestamp, pd.Period)):
        return str(x)
    return x


def run(raw_dir: Path = config.RAW_DIR, tables_dir: Path = config.TABLES_DIR, figures_dir: Path = config.FIGURES_DIR,
        processed_dir: Path = config.PROCESSED_DIR, reports_dir: Path = config.REPORTS_DIR, log=print) -> dict:
    t0 = time.time()
    for d in (tables_dir, figures_dir, processed_dir, reports_dir):
        Path(d).mkdir(parents=True, exist_ok=True)
    T = lambda name: Path(tables_dir) / name
    F = lambda name: Path(figures_dir) / name
    K: dict = {"tanimlar": {
        "gecerli_siparis_bitis": str(config.END), "rfm_tarihi": str(config.SNAPSHOT.date()),
        "gozlem_sonu": str(config.OBS_END.date()), "kohort_baslangic": str(config.COHORT_START),
        "son_tam_ay": str(config.LAST_FULL_MONTH), "churn_esikleri": list(config.CHURN_WINDOWS),
        "ana_churn_esigi": config.MAIN_CHURN_WINDOW}}

    # ---------------------------------------------------------- 1. veri
    log("1/6 Veri yükleniyor ve temizleniyor...")
    raw = data.load_raw(raw_dir)
    o, it, cust, filt = data.build_tables(raw)
    K["veri"] = {"ham_tablo_boyutlari": data.raw_sizes(raw), "filtre": filt,
                 "siparis": int(len(o)), "musteri": int(len(cust)), "ciro": float(o["order_value"].sum()),
                 "ort_siparis_degeri": float(o["order_value"].mean()),
                 "ilk_siparis": str(o["purchase_ts"].min()), "son_siparis": str(o["purchase_ts"].max()),
                 "tek_alisveris_gunu_%": float((cust["n_days"] == 1).mean() * 100),
                 "birden_fazla_siparis_%": float((cust["n_orders"] >= 2).mean() * 100),
                 "birden_fazla_alisveris_gunu_%": float((cust["n_days"] >= 2).mean() * 100)}
    daily = o.groupby("purchase_date").size()
    K["veri"]["gunluk_siparis_son_gunler"] = {str(k.date()): int(v) for k, v in daily.loc["2018-08-15":].items()}
    first_day = o.merge(cust[["first_date"]], left_on="customer_unique_id", right_index=True)
    first_day = first_day[(first_day["purchase_date"] >= "2018-01-01") & (first_day["purchase_date"] < "2018-08-01")]
    K["veri"]["ocak_temmuz_2018_ilk_gun_ciro_payi_%"] = float(
        first_day.loc[first_day["purchase_date"] == first_day["first_date"], "order_value"].sum()
        / first_day["order_value"].sum() * 100)
    new_per_month = cust[(cust["first_month"] >= pd.Period("2018-01", "M"))
                         & (cust["first_month"] <= pd.Period("2018-07", "M"))].groupby("first_month").size()
    K["veri"]["ocak_temmuz_2018_aylik_yeni_musteri_ort"] = float(new_per_month.mean())

    # ---------------------------------------------------------- 2. kohort + RFM
    log("2/6 Kohort ve RFM...")
    counts, pct, sizes = cohort.retention_matrix(o, cust)
    tbl = pct.copy()
    tbl.insert(0, "kohort_buyuklugu", sizes)
    tbl.index = tbl.index.astype(str)
    tbl.index.name = "kohort"
    _csv(tbl, T("kohort_tutunma.csv"))
    rep_rates = cohort.cohort_repeat_table(cust)
    _csv(rep_rates, T("kohort_tekrar_oranlari.csv"), index=False)
    within = {d: cohort.repeat_within(cust, d) for d in (30, 90, 180, 365)}
    K["kohort"] = {
        "kohort_sayisi": int(len(sizes)), "ilk_kohort": str(sizes.index.min()), "son_kohort": str(sizes.index.max()),
        "agirlikli_tutunma_%": cohort.weighted_retention(counts, sizes),
        "en_yuksek_hucre_%": float(np.nanmax(pct.values)),
        "n_gunde_tekrar_%": {d: v[0] for d, v in within.items()},
        "n_gunde_tekrar_payda": {d: v[1] for d, v in within.items()},
        "ikinci_alima_sure": cohort.gap_stats(cust),
        "kohort_90g_min_%": float(rep_rates["tekrar_90g_%"].min()),
        "kohort_90g_max_%": float(rep_rates["tekrar_90g_%"].max()),
        "kasim_2017_90g_%": float(rep_rates.set_index("kohort").loc["2017-11", "tekrar_90g_%"]),
    }
    plots.cohort_heatmap(pct.set_axis(pct.index.astype(str)), sizes.set_axis(sizes.index.astype(str)),
                         F("fig_kohort_tutunma.png"))

    scored, cuts = rfm.score_rfm(cust)
    scored["segment"] = rfm.assign_segments(scored)
    seg = rfm.segment_summary(scored, o)
    _csv(seg, T("rfm_segmentleri.csv"))
    K["rfm"] = {"kesim_noktalari": cuts, "segmentler": json.loads(seg.reset_index().to_json(orient="records",
                                                                                           force_ascii=False)),
                "yogunlasma": rfm.concentration(scored)}
    plots.rfm_segments(seg, F("fig_rfm_segmentleri.png"))
    data.save_processed(o, it, scored, processed_dir)

    # ---------------------------------------------------------- 3. churn
    log("3/6 Churn (180 ve 365 gün) ve model karşılaştırması...")
    cmp_tbl, det = churn.threshold_comparison(o, scored)
    _csv(cmp_tbl, T("churn_esik_karsilastirma.csv"), index=False)
    K["churn"] = {"esik_karsilastirma": json.loads(cmp_tbl.to_json(orient="records", force_ascii=False))}
    per_window_drv = {}
    for w, dd in det.items():
        drv = churn.driver_table(dd["elig"])
        tests = churn.key_tests(dd["elig"])
        per_window_drv[w] = drv
        _csv(drv, T(f"churn_etkenler_{w}g.csv"), index=False)
        _csv(tests, T(f"churn_testler_{w}g.csv"), index=False)
        _csv(dd["lift"], T(f"churn_model_desil_{w}g.csv"), index=False)
        _csv(dd["coefs"], T(f"churn_model_katsayilar_{w}g.csv"))
        K["churn"][f"{w}g"] = {"populasyon": dd["counts"], "tekrar_alim_%": float(dd["elig"]["y"].mean() * 100),
                               "model": dd["model"],
                               "testler": json.loads(tests.to_json(orient="records", force_ascii=False)),
                               "etkenler": json.loads(drv.to_json(orient="records", force_ascii=False))}
    main = config.MAIN_CHURN_WINDOW
    plots.churn_drivers(per_window_drv[main], K["churn"][f"{main}g"]["tekrar_alim_%"], main,
                        F("fig_churn_etkenler.png"))
    plots.churn_threshold_compare(per_window_drv, F("fig_churn_esik_karsilastirma.png"))
    plots.churn_model_lift(det[main]["lift"], det[main]["model"], F("fig_churn_model_desil.png"))
    K["churn"]["ilk_siparisi_21g_ustu_%"] = float((det[main]["elig"]["delivery_days"] > 21).mean() * 100)

    # ---------------------------------------------------------- 4. sepet
    log("4/6 Sepet analizi...")
    struct = basket.basket_structure(o)
    pairs, n_multi = basket.category_pairs(it, len(o))
    _csv(pairs, T("sepet_ciftleri.csv"), index=False)
    mib = basket.multi_item_by_category(it)
    _csv(mib, T("sepet_kategori_cok_kalem.csv"))
    K["sepet"] = {"yapi": struct, "cok_kategorili_siparis_bilinen": int(n_multi),
                  "cift_sayisi": int(len(pairs)), "cift_min_siparis": int(pairs["birlikte_siparis"].min()),
                  "cift_max_siparis": int(pairs["birlikte_siparis"].max()),
                  "dusuk_orneklemli_cift": int(pairs["dusuk_orneklem"].sum()),
                  "ciftler": json.loads(pairs.to_json(orient="records", force_ascii=False)),
                  "kategori_cok_kalem": json.loads(mib.reset_index().to_json(orient="records", force_ascii=False)),
                  "tekrar_alanlar": basket.repeat_category_behaviour(o, it, scored)}
    plots.basket_pairs(pairs, len(o), F("fig_sepet_ciftleri.png"))

    # ---------------------------------------------------------- 5. tahmin
    log("5/6 Haftalık satış tahmini ve geriye dönük test (birkaç saniye sürebilir)...")
    y_raw = forecast.weekly_series(o)
    bf17, bf18 = config.BLACK_FRIDAY_WEEKS[2017], config.BLACK_FRIDAY_WEEKS[2018]
    y, uplift, bf_raw = forecast.clean_event(y_raw, bf17)
    _csv(pd.DataFrame({"ciro_ham": y_raw, "ciro_temiz": y}).rename_axis("hafta_baslangic"),
         T("tahmin_haftalik_seri.csv"))
    bt = forecast.backtest(y)
    met = forecast.metrics(bt)
    _csv(met, T("tahmin_geriye_donuk_test.csv"), index=False)
    best = met.iloc[0]["model"]
    fdf, total = forecast.final_forecast(y, bt, best, event_uplift=uplift, event_week=bf18)
    base_fdf, base_total = forecast.final_forecast(y, bt, forecast.BASELINE)
    fdf["baslangic_tahmini"] = base_fdf["tahmin_taban"].values
    _csv(fdf.assign(hafta_baslangic=fdf["hafta_baslangic"].dt.strftime("%Y-%m-%d")), T("tahmin_14_hafta.csv"),
         index=False)
    monthly = forecast.monthly_table(o)
    _csv(monthly, T("aylik_ciro.csv"))
    m_full = monthly[monthly["tam_ay"]]
    K["tahmin"] = {
        "yeterlilik": forecast.data_sufficiency(y), "en_iyi_model": best, "baslangic_modeli": forecast.BASELINE,
        "metrikler": json.loads(met.to_json(orient="records", force_ascii=False)),
        "toplam": total, "baslangic_modeli_toplam_taban": base_total["toplam_taban"],
        "haftalik_tahmin_min": float(fdf["tahmin_taban"].min()), "haftalik_tahmin_max": float(fdf["tahmin_taban"].max()),
        "black_friday_2017_hafta_ciro": bf_raw, "black_friday_carpani": float(uplift),
        "tahmin_baslangic": str(fdf["hafta_baslangic"].min().date()),
        "tahmin_bitis": str((fdf["hafta_baslangic"].max() + pd.Timedelta(days=6)).date()),
        "aylik_2018_mart_temmuz_ort": float(monthly.loc["2018-03":"2018-07", "ciro"].mean()),
        "aylik_2018_mart_temmuz_min": float(monthly.loc["2018-03":"2018-07", "ciro"].min()),
        "aylik_2018_mart_temmuz_max": float(monthly.loc["2018-03":"2018-07", "ciro"].max()),
        "ocak_temmuz_2017": float(m_full.loc["2017-01":"2017-07", "ciro"].sum()),
        "ocak_temmuz_2018": float(m_full.loc["2018-01":"2018-07", "ciro"].sum()),
    }
    K["tahmin"]["ocak_temmuz_degisim_%"] = (K["tahmin"]["ocak_temmuz_2018"] / K["tahmin"]["ocak_temmuz_2017"] - 1) * 100
    plots.forecast(y_raw, fdf, met, best, bf17, uplift, config.LAST_FULL_WEEK, F("fig_tahmin.png"),
                   base_fdf=base_fdf)

    # ---------------------------------------------------------- 6. çıktılar
    log("6/6 Sonuçlar ve yönetici özeti yazılıyor...")
    K = _jsonable(K)
    with open(Path(tables_dir) / "sonuclar.json", "w", encoding="utf-8") as f:
        json.dump(K, f, ensure_ascii=False, indent=2)   # süre yazılmaz: aynı veri = aynı dosya
    report.write_report(K, Path(reports_dir) / "yonetici_ozeti.md")
    K["sure_saniye"] = round(time.time() - t0, 1)
    return K
