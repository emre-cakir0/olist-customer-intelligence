"""Birim testleri: tanımlar sentetik veride bilinen sonuçları veriyor mu?"""
import numpy as np
import pandas as pd
import pytest

from olist_ci import basket, churn, cohort, data, forecast, rfm


# ------------------------------------------------------------------ veri
def test_eksik_ham_veri_acik_hata_verir(tmp_path):
    with pytest.raises(data.VeriEksikHatasi) as e:
        data.load_raw(tmp_path)
    msg = str(e.value)
    assert "olist_orders_dataset.csv" in msg and "kaggle" in msg.lower()


def test_gecerli_siparis_filtresi(toy_tables):
    o, it, cust, filt = toy_tables
    assert set(o["order_id"]) == {"o1", "o2", "o3", "o4", "o5", "o6", "o8"}   # o7 iptal, o9 bitişten sonra
    assert filt["iptal_ulasilamaz_olusturuldu"] == 1 and filt["bitis_tarihinden_sonra"] == 1
    # ödeme tutarı = fiyat + kargo
    assert o.set_index("order_id").loc["o1", "order_value"] == pytest.approx(165.0)


def test_musteri_birlestirme_ve_tekrar_alim_tanimi(toy_tables):
    _, _, cust, _ = toy_tables
    a = cust.loc["A"]
    assert a["n_orders"] == 3 and a["n_days"] == 2           # aynı gün iki sipariş = bir alışveriş günü
    assert a["second_date"] == pd.Timestamp("2017-03-05")     # aynı gün sipariş tekrar alım sayılmaz
    assert a["gap_days"] == 54
    assert pd.isna(cust.loc["B", "second_date"])
    assert cust.loc["D", "n_orders"] == 1                      # iptal edilen sipariş sayılmaz
    assert cust.loc["A", "first_category"] == "bed_bath_table"


# ------------------------------------------------------------------ kohort
def test_kohort_ilk_siparis_ayina_gore(toy_tables):
    o, _, cust, _ = toy_tables
    counts, pct, sizes = cohort.retention_matrix(o, cust, start=pd.Period("2017-01", "M"),
                                                 last_full_month=pd.Period("2017-06", "M"), max_offset=12)
    assert sizes.to_dict() == {pd.Period("2017-01", "M"): 2, pd.Period("2017-02", "M"): 2}
    # A: Ocak kohortu, Mart'ta (2. ay) döndü -> 1/2 = %50
    assert pct.loc[pd.Period("2017-01", "M"), 2] == pytest.approx(50.0)
    assert pct.loc[pd.Period("2017-01", "M"), 1] == 0
    # Ocak + 6 ay = Temmuz > son tam ay (Haziran) -> gözlenmedi
    assert np.isnan(pct.loc[pd.Period("2017-01", "M"), 6])
    assert np.isnan(pct.loc[pd.Period("2017-02", "M"), 5])


def test_n_gun_icinde_tekrar_yalnizca_kapanmis_pencere(toy_tables):
    _, _, cust, _ = toy_tables
    rate, denom = cohort.repeat_within(cust, 90, obs_end=pd.Timestamp("2017-05-10"))
    # Penceresi kapanan: A (01-10), B (01-20), C (02-03); D (02-16 + 90 = 05-17) açık
    assert denom == 3 and rate == pytest.approx(100 / 3)


# ------------------------------------------------------------------ RFM
def test_rfm_puanlari_ve_segmentler():
    rng = np.random.default_rng(0)
    c = pd.DataFrame({"recency_days": rng.integers(1, 700, 500), "n_days": rng.choice([1, 1, 1, 2, 3], 500),
                      "monetary": rng.gamma(2, 80, 500), "n_orders": 1})
    s, cuts = rfm.score_rfm(c)
    assert s["r_score"].between(1, 5).all() and s["m_score"].between(1, 5).all()
    assert len(cuts["R_sinirlari_gun"]) == 4
    # en yakın dilimdeki müşterilerin R puanı 5
    assert s.loc[s["R"] <= cuts["R_sinirlari_gun"][0], "r_score"].eq(5).all()
    seg = rfm.assign_segments(s)
    assert seg.isin(rfm.SEGMENT_ORDER).all()
    assert seg[(s["F"] >= 2) & (s["r_score"] >= 4)].eq("Şampiyonlar").all()
    assert seg[(s["F"] == 1) & (s["r_score"] <= 2) & (s["m_score"] <= 3)].eq("Kayıp - standart").all()
    s["segment"] = seg
    summ = rfm.segment_summary(s, pd.DataFrame({"customer_unique_id": [], "review_score": []}))
    assert summ["musteri"].sum() == 500
    assert summ["ciro_payi_%"].sum() == pytest.approx(100)


# ------------------------------------------------------------------ churn
def test_churn_etiketi_ve_pencere(toy_tables):
    o, _, cust, _ = toy_tables
    obs = pd.Timestamp("2018-08-21")
    e180, cnt = churn.churn_population(o, cust, 180, obs)
    y = e180["y"].to_dict()
    assert y["A"] == 1          # teslimattan 49 gün sonra döndü
    assert y["C"] == 0          # 296 gün sonra döndü: 180 günde kayıp
    assert y["B"] == 0
    e365, _ = churn.churn_population(o, cust, 365, obs)
    assert e365["y"].to_dict()["C"] == 1    # 365 günlük pencerede geri dönmüş sayılır
    # pencere gözlem sonundan önce kapanmamışsa müşteri dışarıda kalır
    e_short, _ = churn.churn_population(o, cust, 180, pd.Timestamp("2017-07-20"))
    assert "D" not in e_short.index and "A" in e_short.index


def test_iki_oran_testi():
    assert churn.two_prop_p(50, 1000, 50, 1000) == pytest.approx(1.0)
    assert churn.two_prop_p(100, 1000, 50, 1000) < 0.001
    assert churn.two_prop_p(100, 1000, 50, 1000) == pytest.approx(churn.two_prop_p(50, 1000, 100, 1000))


def test_wilson_araligi():
    lo, hi = data.wilson(5, 100)
    assert lo < 0.05 < hi and 0 <= lo and hi <= 1


# ------------------------------------------------------------------ sepet
def test_sepet_destek_guven_lift():
    # 4 sipariş: {a,b}, {a,b}, {a,c}, {c}
    items = pd.DataFrame({"order_id": ["1", "1", "2", "2", "3", "3", "4"],
                          "order_item_id": [1, 2, 1, 2, 1, 2, 1],
                          "product_id": list("xyxyxzz"),
                          "category_en": ["a", "b", "a", "b", "a", "c", "c"]})
    pairs, nm = basket.category_pairs(items, n_orders=4, min_pair=1, low_sample=30)
    ab = pairs.set_index(["kategori_A", "kategori_B"]).loc[("a", "b")]
    assert nm == 3
    assert ab["destek_%"] == pytest.approx(50.0)            # 2/4
    assert ab["guven_A_B_%"] == pytest.approx(200 / 3)      # 2/3
    assert ab["guven_B_A_%"] == pytest.approx(100.0)        # 2/2
    assert ab["lift_tum_siparis"] == pytest.approx(0.5 / (0.75 * 0.5))
    assert bool(ab["dusuk_orneklem"]) is True


# ------------------------------------------------------------------ tahmin
def test_geriye_donuk_test_gelecegi_gormez():
    y = pd.Series(np.arange(1, 41, dtype=float), index=pd.date_range("2020-01-06", periods=40, freq="7D"))
    seen = []

    def spy(hist, h):
        seen.append(len(hist))
        return np.repeat(hist[-1], h)

    bt = forecast.backtest(y, models={"spy": spy}, horizon=3, min_train=30)
    # her başlangıçta yalnızca o noktaya kadarki gözlemler kullanılır
    for (_, row) in bt[bt.h == 1].iterrows():
        origin_pos = y.index.get_loc(row["baslangic"])
        assert row["tahmin"] == y.iloc[origin_pos]          # son görülen değer
        assert row["gercek"] == y.iloc[origin_pos + 1]
    assert min(seen) == 30 and max(seen) == 38


def test_naif_tahmin_ve_wape():
    f = forecast.naive_mean(4)
    assert f(np.array([1, 2, 3, 4, 5.0]), 2).tolist() == [3.5, 3.5]
    d = pd.DataFrame({"gercek": [100.0, 100.0], "tahmin": [90.0, 120.0]})
    d["mutlak_hata"] = (d.gercek - d.tahmin).abs()
    assert forecast.wape(d) == pytest.approx(15.0)
    assert forecast.bias(d) == pytest.approx(5.0)


def test_olay_temizleme():
    y = pd.Series([100.0, 120.0, 500.0, 110.0], index=pd.date_range("2017-11-06", periods=4, freq="7D"))
    yc, uplift, raw = forecast.clean_event(y, pd.Timestamp("2017-11-20"))
    assert yc.iloc[2] == 110.0 and uplift == pytest.approx(500 / 110) and raw == 500.0
