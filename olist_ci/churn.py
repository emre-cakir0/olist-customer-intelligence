"""Müşteri kaybı (churn).

Tanım: İlk siparişin TESLİMATINDAN sonraki W gün içinde yeni bir günde sipariş vermeyen müşteri "kayıp" sayılır.
W için 180 ve 365 gün karşılaştırılır.
  * Teslimattan önce ikinci alışverişi yapmış müşteriler dışarıda kalır (ilk deneyim henüz oluşmamıştır).
  * Yalnızca W günlük penceresi gözlem sonundan (config.OBS_END) önce kapanmış müşteriler sayılır.
  * İlk teslimatı 2017'den önce olan seyrek 2016 müşterileri dahil edilmez.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import norm
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

from . import config
from .data import wilson

POP_START = pd.Timestamp("2017-01-01")


def churn_population(orders: pd.DataFrame, customers: pd.DataFrame, window: int,
                     obs_end: pd.Timestamp = config.OBS_END):
    """Analiz popülasyonu ve hedef değişken (y = 1: W gün içinde geri döndü).

    Döndürür: (uygun_musteriler, popülasyon_sayimlari)
    """
    first = (orders.sort_values(["customer_unique_id", "purchase_ts"])
             .drop_duplicates("customer_unique_id").set_index("customer_unique_id"))
    d = first.join(customers[["first_date", "second_date", "n_days"]])
    n_all = len(d)
    d = d[d["delivered_ts"].notna()].copy()
    n_deliv = len(d)
    d["deliv_date"] = d["delivered_ts"].dt.normalize()
    early = d["second_date"].notna() & (d["second_date"] <= d["deliv_date"])
    d = d[~early].copy()
    d["days_to_repeat"] = (d["second_date"] - d["deliv_date"]).dt.days
    d["y"] = ((d["days_to_repeat"] > 0) & (d["days_to_repeat"] <= window)).astype(int)
    closed = d["deliv_date"] + pd.Timedelta(days=window) <= obs_end
    elig = d[(d["deliv_date"] >= POP_START) & closed].copy()
    counts = {"tum_musteri": int(n_all), "ilk_siparisi_teslim_edilen": int(n_deliv),
              "teslimattan_once_tekrar_alan_cikarilan": int(early.sum()),
              "penceresi_kapanmis": int(len(elig)), "geri_donen": int(elig["y"].sum())}
    return elig, counts


def two_prop_p(k1: int, n1: int, k2: int, n2: int) -> float:
    """İki oranın farkı için çift yönlü z testi p değeri (havuzlanmış varyans)."""
    if min(n1, n2) == 0:
        return np.nan
    p = (k1 + k2) / (n1 + n2)
    se = np.sqrt(p * (1 - p) * (1 / n1 + 1 / n2))
    if se == 0:
        return np.nan
    z = (k1 / n1 - k2 / n2) / se
    return float(2 * norm.sf(abs(z)))


def _rate_row(elig, factor, label, mask):
    sub = elig[mask]
    n, k = len(sub), int(sub["y"].sum())
    lo, hi = wilson(k, n)
    return {"faktor": factor, "seviye": label, "n": n, "geri_donen": k,
            "tekrar_alim_%": k / n * 100 if n else np.nan, "ga_alt_%": lo * 100, "ga_ust_%": hi * 100}


def delivery_buckets(elig):
    dv = elig["delivery_days"]
    return [("≤7 gün", dv <= 7), ("8-14 gün", (dv > 7) & (dv <= 14)),
            ("15-21 gün", (dv > 14) & (dv <= 21)), (">21 gün", dv > 21)]


def driver_table(elig: pd.DataFrame) -> pd.DataFrame:
    """Etken başına geri dönüş oranı ve %95 Wilson güven aralığı. İlişkidir, nedensellik değildir."""
    rows = []
    rs = elig["review_score"].round()
    for s in [1, 2, 3, 4, 5]:
        rows.append(_rate_row(elig, "Yorum puanı", str(s), rs == s))
    rows.append(_rate_row(elig, "Yorum puanı", "yorum yok", rs.isna()))
    dl = elig["delay_days"]
    for lab, m in [("zamanında / erken", dl <= 0), ("1-7 gün gecikmiş", (dl > 0) & (dl <= 7)),
                   (">7 gün gecikmiş", dl > 7)]:
        rows.append(_rate_row(elig, "Teslimat gecikmesi", lab, m))
    for lab, m in delivery_buckets(elig):
        rows.append(_rate_row(elig, "Teslimat süresi", lab, m))
    q = elig["order_value"].quantile([.25, .5, .75]).tolist()
    v = elig["order_value"]
    for lab, m in [(f"≤R${q[0]:.0f}", v <= q[0]), (f"R${q[0]:.0f}-{q[1]:.0f}", (v > q[0]) & (v <= q[1])),
                   (f"R${q[1]:.0f}-{q[2]:.0f}", (v > q[1]) & (v <= q[2])), (f">R${q[2]:.0f}", v > q[2])]:
        rows.append(_rate_row(elig, "İlk sipariş tutarı (çeyrek)", lab, m))
    for lab, m in [("1", elig["n_items"] == 1), ("2", elig["n_items"] == 2), ("3+", elig["n_items"] >= 3)]:
        rows.append(_rate_row(elig, "Kalem sayısı", lab, m))
    for p in ["credit_card", "boleto", "voucher", "debit_card"]:
        rows.append(_rate_row(elig, "Ödeme yöntemi", p, elig["pay_type"] == p))
    for c in elig["first_category"].value_counts().head(10).index:
        rows.append(_rate_row(elig, "İlk siparişin kategorisi (en büyük 10)", c, elig["first_category"] == c))
    return pd.DataFrame(rows)


def key_tests(elig: pd.DataFrame) -> pd.DataFrame:
    """Raporda kullanılan ikili karşılaştırmalar (çoklu karşılaştırma düzeltmesi yapılmaz)."""
    dv, dl, rs = elig["delivery_days"], elig["delay_days"], elig["review_score"].round()
    cat = elig["first_category"]
    pairs = [
        ("Teslimat ≤7 gün vs >21 gün", dv <= 7, dv > 21),
        ("Zamanında vs >7 gün gecikmiş", dl <= 0, dl > 7),
        ("Yorum 5 vs 1", rs == 5, rs == 1),
        ("3+ kalem vs 1 kalem", elig["n_items"] >= 3, elig["n_items"] == 1),
        ("bed_bath_table vs cool_stuff", cat == "bed_bath_table", cat == "cool_stuff"),
    ]
    rows = []
    for name, a, b in pairs:
        k1, n1, k2, n2 = int(elig.loc[a, "y"].sum()), int(a.sum()), int(elig.loc[b, "y"].sum()), int(b.sum())
        rows.append({"karsilastirma": name, "n_A": n1, "oran_A_%": k1 / n1 * 100 if n1 else np.nan,
                     "n_B": n2, "oran_B_%": k2 / n2 * 100 if n2 else np.nan,
                     "fark_puan": (k1 / n1 - k2 / n2) * 100 if n1 and n2 else np.nan,
                     "p_degeri": two_prop_p(k1, n1, k2, n2)})
    t = pd.DataFrame(rows)
    # Bonferroni: aynı tabloda 5 karşılaştırma yapıldığı için p değeri 5 ile çarpılır (en fazla 1)
    t["p_bonferroni"] = (t["p_degeri"] * len(t)).clip(upper=1)
    t["anlamli_0_05_duzeltilmis"] = t["p_bonferroni"] < 0.05
    return t


# ------------------------------------------------------------------ model
CONT = ["yorum_puani", "gecikme_gun", "teslim_suresi_gun", "log_siparis_tutari", "kargo_payi", "kalem_sayisi",
        "taksit"]


def features(df: pd.DataFrame, top_states, top_cats) -> pd.DataFrame:
    X = pd.DataFrame(index=df.index)
    X["yorum_puani"] = df["review_score"].fillna(5)
    X["yorum_yok"] = df["review_score"].isna().astype(int)
    X["dusuk_yorum"] = (df["review_score"] <= 2).astype(int)
    X["gecikme_gun"] = df["delay_days"].clip(-30, 30).fillna(0)
    X["gec_teslim"] = (df["delay_days"] > 0).astype(int)
    X["teslim_suresi_gun"] = df["delivery_days"].clip(0, 60)
    X["log_siparis_tutari"] = np.log1p(df["order_value"])
    fs = (df["freight_sum"] / (df["price_sum"] + df["freight_sum"])).clip(0, 1)
    X["kargo_payi"] = fs.fillna(fs.median())
    X["kalem_sayisi"] = df["n_items"].clip(upper=5)
    X["cok_kategori"] = (df["n_categories"] >= 2).astype(int)
    X["taksit"] = df["installments"].clip(upper=12).fillna(1)
    for p in ["boleto", "voucher", "debit_card"]:          # referans: kredi kartı
        X[f"odeme_{p}"] = (df["pay_type"] == p).astype(int)
    for s in top_states:
        X[f"eyalet_{s}"] = (df["customer_state"] == s).astype(int)
    for c in top_cats:
        X[f"kat_{c}"] = (df["first_category"] == c).astype(int)
    return X


def auc_with_ci(y, score, rng, n_boot: int = 300):
    a = float(roc_auc_score(y, score))
    idx = np.arange(len(y))
    bs = []
    for _ in range(n_boot):
        s = rng.choice(idx, len(idx))
        if y[s].sum() in (0, len(s)):
            continue
        bs.append(roc_auc_score(y[s], score[s]))
    return a, float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))


def model_vs_baseline(elig: pd.DataFrame, train_end: pd.Timestamp, seed: int = config.RANDOM_SEED):
    """Zaman sıralı doğrulama: teslim tarihi ≤ train_end eğitim, sonrası test.

    Model: lojistik regresyon (sürekli değişkenler eğitim setine göre standartlaştırılır).
    Başlangıç modelleri: (1) sabit tahmin, AUC = 0,5; (2) tek değişkenli kural "teslimat ne kadar kısaysa
    geri dönüş o kadar olası" (eğitim gerektirmez).
    """
    rng = np.random.default_rng(seed)
    tr = (elig["deliv_date"] <= train_end).values
    te = ~tr
    top_states = elig.loc[tr, "customer_state"].value_counts().head(6).index.tolist()
    top_cats = elig.loc[tr, "first_category"].value_counts().head(12).index.tolist()
    X = features(elig, top_states, top_cats)
    y = elig["y"].values
    mu, sd = X.loc[tr, CONT].mean(), X.loc[tr, CONT].std().replace(0, 1)
    Xs = X.copy()
    Xs[CONT] = (Xs[CONT] - mu) / sd
    lr = LogisticRegression(C=0.5, max_iter=2000).fit(Xs[tr], y[tr])
    p = lr.predict_proba(Xs[te])[:, 1]
    yt = y[te]
    base_score = -X.loc[te, "teslim_suresi_gun"].fillna(X.loc[tr, "teslim_suresi_gun"].median()).values
    a_lr = auc_with_ci(yt, p, rng)
    a_base = auc_with_ci(yt, base_score, rng)

    order = np.argsort(-p, kind="stable")
    dec = np.array_split(order, 10)
    tb = yt.mean()
    lift = pd.DataFrame([{"desil": i, "n": len(ix), "tekrar_alim_%": yt[ix].mean() * 100,
                          "lift": yt[ix].mean() / tb} for i, ix in enumerate(dec, 1)])
    coef = pd.Series(lr.coef_[0], index=Xs.columns)
    coefs = pd.DataFrame({"katsayi": coef, "odds_orani": np.exp(coef)}).sort_values("katsayi")
    coefs.index.name = "degisken"
    res = {
        "egitim_bitis": str(train_end.date()),
        "egitim_n": int(tr.sum()), "egitim_pozitif": int(y[tr].sum()),
        "test_n": int(te.sum()), "test_pozitif": int(yt.sum()), "test_taban_%": float(tb * 100),
        "auc_lojistik": a_lr[0], "auc_lojistik_ga": [a_lr[1], a_lr[2]],
        "auc_baslangic_teslimat_kurali": a_base[0], "auc_baslangic_ga": [a_base[1], a_base[2]],
        "auc_sabit_tahmin": 0.5,
        "ilk_desil_yakalama_%": float(yt[dec[0]].sum() / yt.sum() * 100),
        "ilk_3_desil_yakalama_%": float(sum(yt[ix].sum() for ix in dec[:3]) / yt.sum() * 100),
        "ilk_desil_lift": float(lift.loc[0, "lift"]),
    }
    return res, lift, coefs


def lapsed_shares(customers: pd.DataFrame, windows=config.CHURN_WINDOWS) -> dict[int, float]:
    """Durum bazlı görünüm: son alışverişi W günden eski müşteri payı (%)."""
    return {w: float((customers["recency_days"] > w).mean() * 100) for w in windows}


def threshold_comparison(orders, customers, windows=config.CHURN_WINDOWS, obs_end=config.OBS_END,
                         train_end=config.CHURN_TRAIN_END):
    """Eşik seçiminin sonuçları nasıl değiştirdiğini tek tabloda toplar."""
    gaps = customers["gap_days"].dropna()
    lapsed = lapsed_shares(customers, windows)
    rows, details = [], {}
    for w in windows:
        elig, cnt = churn_population(orders, customers, w, obs_end)
        dv = elig["delivery_days"]
        fast, slow = elig[dv <= 7], elig[dv > 21]
        model, lift, coefs = model_vs_baseline(elig, train_end[w])
        rate = elig["y"].mean() * 100
        rows.append({
            "esik_gun": w,
            "son_alimi_esikten_eski_musteri_%": lapsed[w],
            "tekrar_alanlarin_esik_icinde_donen_payi_%": float((gaps <= w).mean() * 100),
            "penceresi_kapanmis_musteri": cnt["penceresi_kapanmis"],
            "en_gec_ilk_teslimat": str((obs_end - pd.Timedelta(days=w)).date()),
            "geri_donen": cnt["geri_donen"],
            "tekrar_alim_%": float(rate), "churn_%": float(100 - rate),
            "teslimat_7g_alti_tekrar_%": float(fast["y"].mean() * 100),
            "teslimat_21g_ustu_tekrar_%": float(slow["y"].mean() * 100),
            "teslimat_farki_p": two_prop_p(int(fast["y"].sum()), len(fast), int(slow["y"].sum()), len(slow)),
            "model_auc": model["auc_lojistik"], "baslangic_auc": model["auc_baslangic_teslimat_kurali"],
            "model_test_n": model["test_n"], "model_test_pozitif": model["test_pozitif"],
        })
        details[w] = {"elig": elig, "counts": cnt, "model": model, "lift": lift, "coefs": coefs}
    return pd.DataFrame(rows), details
