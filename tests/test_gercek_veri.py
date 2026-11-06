"""Gerçek veriyle tutarlılık kontrolleri.

Ham CSV'ler (data/raw) ve hat çıktıları (outputs/tables) yoksa bu testler atlanır.
Temel rakamlar ana hattan bağımsız olarak, doğrudan ham CSV'lerden yeniden hesaplanır.
"""
import json
from functools import lru_cache

import numpy as np
import pandas as pd
import pytest

from olist_ci import config, data, rfm

pytestmark = pytest.mark.skipif(
    bool(data.missing_raw_files()) or not (config.TABLES_DIR / "sonuclar.json").is_file(),
    reason="Ham veri veya hat çıktıları yok: önce data/raw'a CSV'leri koyup `python run_pipeline.py` çalıştırın.")


@lru_cache(maxsize=1)
def K():
    with open(config.TABLES_DIR / "sonuclar.json", encoding="utf-8") as f:
        return json.load(f)


def T(name, **kw):
    return pd.read_csv(config.TABLES_DIR / name, encoding="utf-8-sig", **kw)


@lru_cache(maxsize=1)
def independent():
    """Ana hattın kodunu kullanmadan, ham CSV'lerden geçerli siparişleri yeniden kurar."""
    R = config.RAW_DIR
    orders = pd.read_csv(R / "olist_orders_dataset.csv", parse_dates=["order_purchase_timestamp"])
    cust = pd.read_csv(R / "olist_customers_dataset.csv")
    items = pd.read_csv(R / "olist_order_items_dataset.csv")
    pay = pd.read_csv(R / "olist_order_payments_dataset.csv")
    val = pay.groupby("order_id")["payment_value"].sum()
    ok = (~orders["order_status"].isin(["canceled", "unavailable", "created"])
          & orders["order_id"].isin(items["order_id"]) & orders["order_id"].isin(val.index)
          & (orders["order_purchase_timestamp"] <= "2018-08-31 23:59:59"))
    o = orders[ok].merge(cust, on="customer_id")
    o["value"] = o["order_id"].map(val)
    o["day"] = o["order_purchase_timestamp"].dt.normalize()
    return o, items


def test_siparis_musteri_ciro_bagimsiz_hesapla_ayni():
    o, _ = independent()
    v = K()["veri"]
    assert v["siparis"] == len(o)
    assert v["musteri"] == o["customer_unique_id"].nunique()
    assert v["ciro"] == pytest.approx(o["value"].sum(), rel=1e-9)
    days = o.groupby("customer_unique_id")["day"].nunique()
    assert v["tek_alisveris_gunu_%"] == pytest.approx((days == 1).mean() * 100, abs=1e-4)


def test_segmentler_tum_musterileri_bir_kez_kapsar():
    seg = T("rfm_segmentleri.csv", index_col=0)
    assert seg["musteri"].sum() == K()["veri"]["musteri"]
    assert seg["musteri_payi_%"].sum() == pytest.approx(100, abs=0.01)
    assert seg["ciro_payi_%"].sum() == pytest.approx(100, abs=0.01)
    assert seg["ciro"].sum() == pytest.approx(K()["veri"]["ciro"], rel=1e-6)
    assert list(seg.index) == [s for s in rfm.SEGMENT_ORDER if s in seg.index]


def test_kohort_tablosu_mantikli():
    coh = T("kohort_tutunma.csv", index_col=0)
    vals = coh.drop(columns="kohort_buyuklugu")
    observed = vals.stack().dropna()
    assert len(observed) > 0 and (observed >= 0).all() and (observed <= 100).all()
    # son kohortun yalnızca ilk ayı gözlenebilir; sonrası boş
    assert vals.iloc[-1].notna().sum() == 1
    assert coh.index[0] == str(config.COHORT_START)


def test_churn_esikleri_tutarli():
    c = T("churn_esik_karsilastirma.csv").set_index("esik_gun")
    assert c.loc[180, "penceresi_kapanmis_musteri"] > c.loc[365, "penceresi_kapanmis_musteri"]
    assert c.loc[365, "tekrar_alanlarin_esik_icinde_donen_payi_%"] > c.loc[180, "tekrar_alanlarin_esik_icinde_donen_payi_%"]
    assert (c["tekrar_alim_%"] + c["churn_%"]).round(6).eq(100).all()
    for w in (180, 365):
        m = K()["churn"][f"{w}g"]["model"]
        assert 0.5 <= m["auc_lojistik"] < 0.7, "AUC beklenenden farklı: rapor dilini gözden geçirin"
        assert m["auc_lojistik_ga"][0] <= m["auc_lojistik"] <= m["auc_lojistik_ga"][1]


def test_sepet_cifti_ham_veriden_sayilir():
    _, items = independent()
    pairs = T("sepet_ciftleri.csv")
    assert (pairs["birlikte_siparis"] >= config.MIN_PAIR_ORDERS).all()
    assert (pairs[["guven_A_B_%", "guven_B_A_%"]] <= 100).all().all()
    # en sık çifti ham tablolardan bağımsız say
    top = pairs.iloc[0]
    o, _ = independent()
    prod = pd.read_csv(config.RAW_DIR / "olist_products_dataset.csv")
    tr = pd.read_csv(config.RAW_DIR / "product_category_name_translation.csv", encoding="utf-8-sig")
    tr.columns = ["product_category_name", "en"]
    it = items[items["order_id"].isin(o["order_id"])].merge(prod, on="product_id").merge(tr, on="product_category_name")
    sets = it.groupby("order_id")["en"].agg(set)
    n_ab = sets.apply(lambda s: top["kategori_A"] in s and top["kategori_B"] in s).sum()
    assert n_ab == top["birlikte_siparis"]


def test_tahmin_serisi_ve_test_tutarli():
    o, _ = independent()
    s = T("tahmin_haftalik_seri.csv", parse_dates=["hafta_baslangic"])
    assert len(s) == K()["tahmin"]["yeterlilik"]["hafta_sayisi"]
    end = s["hafta_baslangic"].max() + pd.Timedelta(days=6)
    rng = o[(o["day"] >= s["hafta_baslangic"].min()) & (o["day"] <= end)]
    assert s["ciro_ham"].sum() == pytest.approx(rng["value"].sum(), rel=1e-9)
    bt = T("tahmin_geriye_donuk_test.csv")
    assert bt["test_sayisi"].nunique() == 1
    assert bt["baslangic_modeli"].sum() == 1
    fc = T("tahmin_14_hafta.csv")
    assert len(fc) == config.FORECAST_HORIZON
    assert (fc["alt_%10"] <= fc["tahmin_taban"]).all() and (fc["tahmin_taban"] <= fc["ust_%90"]).all()


def test_rapor_guncel_sayilari_iceriyor():
    rep = (config.REPORTS_DIR / "yonetici_ozeti.md").read_text(encoding="utf-8")
    v = K()["veri"]
    assert f"{v['musteri']:,}".replace(",", ".") in rep
    c180 = K()["churn"]["esik_karsilastirma"][0]
    assert f"{c180['penceresi_kapanmis_musteri']:,}".replace(",", ".") in rep
    assert "ROI" in rep and "genellenmemelidir" in rep
    assert np.isfinite(K()["tahmin"]["toplam"]["toplam_taban"])
