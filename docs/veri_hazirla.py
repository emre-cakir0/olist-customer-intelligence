"""Olist uygulamasının veri dosyasını (veri.js) proje çıktılarından üretir.

Kullanım (uygulama klasöründen):
    python veri_hazirla.py "<olist-customer-intelligence proje klasörü>"

Okunanlar: data/processed/*.csv.gz ve outputs/tables/* (önce projede `python run_pipeline.py` çalışmış olmalı).
Yazılan: veri.js  (tarayıcının dosyayı doğrudan açabilmesi için JSON, bir JavaScript değişkeni olarak).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

KATEGORI_TR = {
    "agro_industry_and_commerce": "Tarım, sanayi ve ticaret",
    "air_conditioning": "Klima",
    "art": "Sanat",
    "arts_and_craftmanship": "El sanatları",
    "audio": "Ses sistemleri",
    "auto": "Otomotiv",
    "baby": "Bebek",
    "bed_bath_table": "Yatak, banyo ve sofra",
    "books_general_interest": "Kitap (genel)",
    "books_imported": "Kitap (ithal)",
    "books_technical": "Kitap (teknik)",
    "cds_dvds_musicals": "CD, DVD ve müzikal",
    "christmas_supplies": "Yılbaşı ürünleri",
    "cine_photo": "Sinema ve fotoğraf",
    "computers": "Bilgisayar",
    "computers_accessories": "Bilgisayar aksesuarı",
    "consoles_games": "Konsol ve oyun",
    "construction_tools_construction": "Yapı malzemesi",
    "construction_tools_lights": "Aydınlatma (yapı)",
    "construction_tools_safety": "İş güvenliği",
    "cool_stuff": "Hediyelik ilginç ürünler",
    "costruction_tools_garden": "Bahçe yapı aletleri",
    "costruction_tools_tools": "El aletleri",
    "diapers_and_hygiene": "Bebek bezi ve hijyen",
    "drinks": "İçecek",
    "dvds_blu_ray": "DVD ve Blu-ray",
    "electronics": "Elektronik",
    "fashio_female_clothing": "Kadın giyim",
    "fashion_bags_accessories": "Çanta ve aksesuar",
    "fashion_childrens_clothes": "Çocuk giyim",
    "fashion_male_clothing": "Erkek giyim",
    "fashion_shoes": "Ayakkabı",
    "fashion_sport": "Spor giyim",
    "fashion_underwear_beach": "İç giyim ve plaj",
    "fixed_telephony": "Sabit telefon",
    "flowers": "Çiçek",
    "food": "Gıda",
    "food_drink": "Yiyecek ve içecek",
    "furniture_bedroom": "Yatak odası mobilyası",
    "furniture_decor": "Mobilya ve dekorasyon",
    "furniture_living_room": "Oturma odası mobilyası",
    "furniture_mattress_and_upholstery": "Yatak ve döşeme",
    "garden_tools": "Bahçe aletleri",
    "health_beauty": "Sağlık ve güzellik",
    "home_appliances": "Ev aletleri",
    "home_appliances_2": "Ev aletleri (2)",
    "home_comfort_2": "Ev konforu (2)",
    "home_confort": "Ev konforu",
    "home_construction": "Ev tadilatı",
    "housewares": "Ev gereçleri",
    "industry_commerce_and_business": "Sanayi ve iş dünyası",
    "kitchen_dining_laundry_garden_furniture": "Mutfak, çamaşır ve bahçe mobilyası",
    "la_cuisine": "Mutfak (La Cuisine)",
    "luggage_accessories": "Bavul ve seyahat",
    "market_place": "Pazaryeri (karışık)",
    "music": "Müzik",
    "musical_instruments": "Müzik aletleri",
    "office_furniture": "Ofis mobilyası",
    "party_supplies": "Parti malzemeleri",
    "pc_gamer": "Oyun bilgisayarı",
    "perfumery": "Parfüm",
    "pet_shop": "Evcil hayvan",
    "portateis_cozinha_e_preparadores_de_alimentos": "Taşınabilir mutfak aletleri",
    "security_and_services": "Güvenlik ve hizmet",
    "signaling_and_security": "İşaret ve güvenlik",
    "small_appliances": "Küçük ev aletleri",
    "small_appliances_home_oven_and_coffee": "Fırın ve kahve makinesi",
    "sports_leisure": "Spor ve eğlence",
    "stationery": "Kırtasiye",
    "tablets_printing_image": "Tablet ve baskı",
    "telephony": "Cep telefonu ve aksesuar",
    "toys": "Oyuncak",
    "unknown": "Kategorisi bilinmeyen",
    "watches_gifts": "Saat ve hediye",
}

EYALET_TR = {
    "AC": "Acre", "AL": "Alagoas", "AM": "Amazonas", "AP": "Amapá", "BA": "Bahia", "CE": "Ceará",
    "DF": "Federal Bölge (Brasília)", "ES": "Espírito Santo", "GO": "Goiás", "MA": "Maranhão",
    "MG": "Minas Gerais", "MS": "Mato Grosso do Sul", "MT": "Mato Grosso", "PA": "Pará", "PB": "Paraíba",
    "PE": "Pernambuco", "PI": "Piauí", "PR": "Paraná", "RJ": "Rio de Janeiro", "RN": "Rio Grande do Norte",
    "RO": "Rondônia", "RR": "Roraima", "RS": "Rio Grande do Sul", "SC": "Santa Catarina", "SE": "Sergipe",
    "SP": "São Paulo", "TO": "Tocantins",
}

SEGMENTLER = ["Şampiyonlar", "Uyuyan sadıklar", "Yeni - yüksek sepet", "Yeni - standart",
              "Soğuyanlar", "Kayıp - yüksek değerli", "Kayıp - standart"]

ETKEN_SEVIYE_TR = {"credit_card": "Kredi kartı", "boleto": "Boleto (banka havalesi)", "voucher": "Hediye çeki",
                   "debit_card": "Banka kartı", "yorum yok": "Yorum yok"}


def tr_kat(x):
    return KATEGORI_TR.get(x, x)


def yuvarla(o, n=4):
    if isinstance(o, float):
        return None if np.isnan(o) else round(o, n)
    if isinstance(o, dict):
        return {k: yuvarla(v, n) for k, v in o.items()}
    if isinstance(o, list):
        return [yuvarla(v, n) for v in o]
    return o


def oku(proje: Path, ad: str) -> pd.DataFrame:
    return pd.read_csv(proje / "outputs" / "tables" / ad, encoding="utf-8-sig")


def main(proje: Path, hedef: Path):
    c = pd.read_csv(proje / "data/processed/musteriler.csv.gz", parse_dates=["first_date"])
    o = pd.read_csv(proje / "data/processed/siparisler.csv.gz", parse_dates=["purchase_date"])
    S = json.loads((proje / "outputs/tables/sonuclar.json").read_text(encoding="utf-8"))

    # --- müşteri düzeyi, sütun sütun sıkıştırılmış veri (filtreler tarayıcıda hesaplanır)
    c = c.sort_values("first_date").reset_index(drop=True)
    ay0 = pd.Period("2016-09", "M")
    fm = c["first_date"].dt.to_period("M")
    ay_idx = ((fm.dt.year - ay0.year) * 12 + (fm.dt.month - ay0.month)).astype(int)
    aylar = [str(ay0 + i) for i in range(int(ay_idx.max()) + 1)]

    eyaletler = sorted(c["state"].fillna("?").unique())
    c["first_category"] = c["first_category"].fillna("unknown")
    kat_say = c["first_category"].value_counts()
    kategoriler = list(kat_say.index)

    # tekrar alanların, ilk alışveriş gününden sonraki alışveriş aylarının kohort ayına uzaklığı
    oo = o.merge(c[["customer_unique_id", "first_date"]], on="customer_unique_id")
    oo = oo[oo["purchase_date"] > oo["first_date"]]
    pm = oo["purchase_date"].dt.to_period("M")
    fmo = oo["first_date"].dt.to_period("M")
    oo = oo.assign(off=(pm.dt.year * 12 + pm.dt.month) - (fmo.dt.year * 12 + fmo.dt.month))
    idx_of = pd.Series(c.index, index=c["customer_unique_id"])
    tekrar = {}
    for cid, g in oo.groupby("customer_unique_id")["off"]:
        tekrar[int(idx_of[cid])] = sorted(set(int(x) for x in g))

    musteri = {
        "ay": ay_idx.tolist(),
        "eyalet": c["state"].fillna("?").map({e: i for i, e in enumerate(eyaletler)}).tolist(),
        "segment": c["segment"].map({s: i for i, s in enumerate(SEGMENTLER)}).tolist(),
        "kategori": c["first_category"].map({k: i for i, k in enumerate(kategoriler)}).tolist(),
        "gun": c["n_days"].astype(int).tolist(),
        "siparis": c["n_orders"].astype(int).tolist(),
        "harcama_kurus": (c["monetary"] * 100).round().astype(int).tolist(),
        "son_alim_gun": c["recency_days"].astype(int).tolist(),
        "r": c["r_score"].astype(int).tolist(),
        "m": c["m_score"].astype(int).tolist(),
        "ara_gun": c["gap_days"].fillna(-1).astype(int).tolist(),
        "ilk_tarih_gun": (c["first_date"] - pd.Timestamp("2016-09-01")).dt.days.astype(int).tolist(),
        "tekrar_aylar": {str(k): v for k, v in tekrar.items()},
    }

    # --- doğrulama: tarayıcıdaki kohort hesabıyla aynı formül, projedeki tabloyla karşılaştır
    kt = oku(proje, "kohort_tutunma.csv").set_index("kohort")
    son_tam = pd.Period(S["tanimlar"]["son_tam_ay"], "M")
    bas = pd.Period(S["tanimlar"]["kohort_baslangic"], "M")
    sizes = pd.Series(ay_idx).value_counts()
    for kohort, row in kt.iterrows():
        a = (pd.Period(kohort, "M") - ay0).n
        for k in range(1, 13):
            beklenen = row[str(k)]
            if pd.isna(beklenen):
                continue
            pay = sum(1 for i, offs in tekrar.items() if ay_idx[i] == a and k in offs)
            assert abs(pay / sizes[a] * 100 - beklenen) < 1e-3, (kohort, k)

    rfm = oku(proje, "rfm_segmentleri.csv")
    tests180 = oku(proje, "churn_testler_180g.csv")
    tests365 = oku(proje, "churn_testler_365g.csv")
    etk180 = oku(proje, "churn_etkenler_180g.csv")
    etk365 = oku(proje, "churn_etkenler_365g.csv")
    for e in (etk180, etk365):
        e["seviye"] = [tr_kat(s) if f.startswith("İlk siparişin kategorisi") else ETKEN_SEVIYE_TR.get(s, s)
                       for f, s in zip(e["faktor"], e["seviye"])]
    for t in (tests180, tests365):
        t["karsilastirma"] = t["karsilastirma"].str.replace("bed_bath_table", tr_kat("bed_bath_table")) \
            .str.replace("cool_stuff", tr_kat("cool_stuff"))
    desil180 = oku(proje, "churn_model_desil_180g.csv")
    desil365 = oku(proje, "churn_model_desil_365g.csv")
    ciftler = oku(proje, "sepet_ciftleri.csv")
    ciftler["kategori_A"] = ciftler["kategori_A"].map(tr_kat)
    ciftler["kategori_B"] = ciftler["kategori_B"].map(tr_kat)
    cok_kalem = oku(proje, "sepet_kategori_cok_kalem.csv")
    cok_kalem["kategori"] = cok_kalem["kategori"].map(tr_kat)
    seri = oku(proje, "tahmin_haftalik_seri.csv")
    tahmin = oku(proje, "tahmin_14_hafta.csv")
    test = oku(proje, "tahmin_geriye_donuk_test.csv")
    aylik = oku(proje, "aylik_ciro.csv")

    veri = {
        "uretim": pd.Timestamp.now().strftime("%Y-%m-%d"),
        "aylar": aylar,
        "eyaletler": [{"kod": e, "ad": EYALET_TR.get(e, e)} for e in eyaletler],
        "kategoriler": [{"kod": k, "ad": tr_kat(k), "musteri": int(kat_say[k])} for k in kategoriler],
        "segmentler": SEGMENTLER,
        "musteri": musteri,
        "ozet": yuvarla(S, 6),
        "rfm_tablo": yuvarla(rfm.to_dict("records")),
        "churn": {
            "180": {"testler": yuvarla(tests180.to_dict("records")), "etkenler": yuvarla(etk180.to_dict("records")),
                    "desil": yuvarla(desil180.to_dict("records"))},
            "365": {"testler": yuvarla(tests365.to_dict("records")), "etkenler": yuvarla(etk365.to_dict("records")),
                    "desil": yuvarla(desil365.to_dict("records"))},
        },
        "sepet": {"ciftler": yuvarla(ciftler.to_dict("records")), "cok_kalem": yuvarla(cok_kalem.to_dict("records"))},
        "tahmin": {"seri": yuvarla(seri.to_dict("records"), 2), "ileri": yuvarla(tahmin.to_dict("records"), 2),
                   "test": yuvarla(test.to_dict("records"))},
        "aylik": yuvarla(aylik.to_dict("records"), 2),
    }
    hedef.write_text("window.OLIST = " + json.dumps(veri, ensure_ascii=False, separators=(",", ":")) + ";\n",
                     encoding="utf-8")
    print(f"veri.js yazıldı: {hedef.stat().st_size / 1e6:.1f} MB, {len(c)} müşteri, kohort tablosu doğrulandı.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit('Kullanım: python veri_hazirla.py "<olist-customer-intelligence klasörü>"')
    main(Path(sys.argv[1]), Path(__file__).resolve().parent / "veri.js")
