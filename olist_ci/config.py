"""Proje genelindeki yollar, tarihler ve analiz parametreleri.

Tüm tanımlar tek yerde durur; analiz modülleri bu değerleri parametre olarak alır,
böylece başka bir eşik veya tarihle yeniden kullanılabilirler.
"""
from pathlib import Path

import pandas as pd

# ------------------------------------------------------------------ yollar
ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
TABLES_DIR = ROOT / "outputs" / "tables"
FIGURES_DIR = ROOT / "outputs" / "figures"
REPORTS_DIR = ROOT / "reports"

# Gerekli ham dosyalar (Kaggle: olistbr/brazilian-ecommerce)
RAW_FILES = {
    "orders": "olist_orders_dataset.csv",
    "customers": "olist_customers_dataset.csv",
    "items": "olist_order_items_dataset.csv",
    "payments": "olist_order_payments_dataset.csv",
    "reviews": "olist_order_reviews_dataset.csv",
    "products": "olist_products_dataset.csv",
    "translation": "product_category_name_translation.csv",
}

# ------------------------------------------------------------------ analiz penceresi
# Geçerli sipariş: 31 Ağustos 2018'e kadar verilmiş olmalı (Eylül-Ekim 2018'de yalnızca birkaç kayıt var).
END = pd.Timestamp("2018-08-31 23:59:59")
# RFM ve "son alımdan geçen gün" bu tarihe göre hesaplanır (son geçerli siparişten sonraki gün).
SNAPSHOT = pd.Timestamp("2018-09-01")
# Veri 22 Ağustos 2018'den sonra keskin biçimde azalıyor (günde ~250 siparişten 29 Ağustos'ta 11'e).
# Bir müşterinin geri dönüp dönmediğini gözlemlediğimiz her pencere bu günde biter.
OBS_END = pd.Timestamp("2018-08-21")
# Kohortlar: ilk sipariş ayı. 2016'daki birkaç yüz sipariş seyrek olduğundan kohortlar 2017-01'de başlar.
COHORT_START = pd.Period("2017-01", "M")
# Son tam ay (Ağustos 2018 eksik olduğundan tutunma hücrelerinde gözlenmiş sayılmaz).
LAST_FULL_MONTH = pd.Period("2018-07", "M")
COHORT_MAX_OFFSET = 12

# ------------------------------------------------------------------ churn
CHURN_WINDOWS = (180, 365)            # karşılaştırılan eşikler (gün)
MAIN_CHURN_WINDOW = 180               # raporun ana eşiği
# Zaman sıralı model doğrulaması: teslim tarihi bu günden önce olanlar eğitim, sonrası test.
CHURN_TRAIN_END = {180: pd.Timestamp("2017-10-31"), 365: pd.Timestamp("2017-05-31")}
RANDOM_SEED = 42

# ------------------------------------------------------------------ sepet
MIN_PAIR_ORDERS = 10                  # bir kategori çiftinin tabloya girmesi için asgari birlikte sipariş
LOW_SAMPLE_PAIR = 30                  # bunun altındaki çiftler "düşük örneklem" olarak işaretlenir

# ------------------------------------------------------------------ tahmin
SERIES_START = pd.Timestamp("2017-01-02")   # ilk tam hafta (Pazartesi)
LAST_FULL_WEEK = pd.Timestamp("2018-08-13")  # 20 Ağustos haftası eksik veri içerir
FORECAST_HORIZON = 14
MIN_TRAIN_WEEKS = 30
BLACK_FRIDAY_WEEKS = {2017: pd.Timestamp("2017-11-20"), 2018: pd.Timestamp("2018-11-19")}
