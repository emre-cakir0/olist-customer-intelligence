"""Veri yükleme, temizleme ve müşteri düzeyinde birleştirme.

Üç tablo üretir:
  orders     sipariş düzeyi (tutar, kalem, ödeme, yorum, teslimat)
  items      kalem düzeyi (ürün kategorisi İngilizce adıyla)
  customers  müşteri düzeyi (customer_unique_id bazında ilk/son alım, sipariş, alışveriş günü, harcama)
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from . import config


class VeriEksikHatasi(FileNotFoundError):
    """Ham Olist CSV dosyaları bulunamadığında yükseltilir."""


TS_COLS = [
    "order_purchase_timestamp",
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
    "order_estimated_delivery_date",
]


def missing_raw_files(raw_dir: Path | str = config.RAW_DIR) -> list[str]:
    raw_dir = Path(raw_dir)
    return [f for f in config.RAW_FILES.values() if not (raw_dir / f).is_file()]


def raw_missing_message(raw_dir: Path, missing: list[str]) -> str:
    lines = [
        f"Ham veri bulunamadı: {raw_dir}",
        "Eksik dosyalar:",
        *[f"  - {f}" for f in missing],
        "",
        "Nasıl edinilir:",
        "  1) https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce adresinden veri setini indirin",
        "     (Kaggle hesabı gerekir; 'Download' düğmesi bir ZIP verir).",
        "  2) ZIP'i açın ve yukarıdaki CSV'leri data\\raw klasörüne kopyalayın.",
        "  Ayrıntı: data/raw/README.md",
    ]
    return "\n".join(lines)


def load_raw(raw_dir: Path | str = config.RAW_DIR) -> dict[str, pd.DataFrame]:
    """Ham CSV'leri okur. Dosya eksikse VeriEksikHatasi yükseltir (çalıştırma durur)."""
    raw_dir = Path(raw_dir)
    missing = missing_raw_files(raw_dir)
    if missing:
        raise VeriEksikHatasi(raw_missing_message(raw_dir, missing))
    p = lambda key: raw_dir / config.RAW_FILES[key]
    raw = {
        "orders": pd.read_csv(p("orders"), parse_dates=TS_COLS),
        "customers": pd.read_csv(p("customers"), usecols=["customer_id", "customer_unique_id", "customer_state"]),
        "items": pd.read_csv(p("items"), usecols=["order_id", "order_item_id", "product_id", "price", "freight_value"]),
        "payments": pd.read_csv(p("payments")),
        "reviews": pd.read_csv(p("reviews"), usecols=["order_id", "review_score"]),
        "products": pd.read_csv(p("products"), usecols=["product_id", "product_category_name"]),
        # dosyanın başında BOM var; sütunları konumla adlandırmak bunu güvenli kılar
        "translation": pd.read_csv(p("translation"), encoding="utf-8-sig"),
    }
    raw["translation"].columns = ["product_category_name", "category_en"]
    return raw


def raw_sizes(raw: dict[str, pd.DataFrame]) -> dict[str, int]:
    return {k: int(len(v)) for k, v in raw.items() if k != "translation"}


def build_tables(raw: dict[str, pd.DataFrame], end: pd.Timestamp = config.END,
                 snapshot: pd.Timestamp = config.SNAPSHOT):
    """Geçerli siparişleri seçer; sipariş, kalem ve müşteri tablolarını ve filtre özetini döndürür.

    Geçerli sipariş: durumu canceled/unavailable/created olmayan, en az bir kalemi ve ödemesi olan,
    `end` tarihine kadar verilmiş sipariş.
    """
    orders, customers, items = raw["orders"], raw["customers"], raw["items"]
    pay, rev, prod, tr = raw["payments"], raw["reviews"], raw["products"], raw["translation"]

    prod = prod.merge(tr, on="product_category_name", how="left")
    prod["category_en"] = prod["category_en"].fillna(prod["product_category_name"]).fillna("unknown")
    it = items.merge(prod[["product_id", "category_en"]], on="product_id", how="left")
    it["category_en"] = it["category_en"].fillna("unknown")

    agg_items = it.groupby("order_id").agg(
        n_items=("order_item_id", "count"),
        price_sum=("price", "sum"),
        freight_sum=("freight_value", "sum"),
        n_categories=("category_en", "nunique"),
    )
    first_cat = (it.sort_values(["order_id", "order_item_id"]).drop_duplicates("order_id")
                 .set_index("order_id")["category_en"].rename("first_category"))
    pay_agg = pay.groupby("order_id").agg(order_value=("payment_value", "sum"),
                                          installments=("payment_installments", "max"))
    main_pay = (pay.sort_values("payment_value", ascending=False).drop_duplicates("order_id")
                .set_index("order_id")["payment_type"].rename("pay_type"))
    rev_agg = rev.groupby("order_id")["review_score"].mean().rename("review_score")

    o = (orders.merge(customers, on="customer_id", how="left")
         .merge(agg_items, on="order_id", how="left")
         .merge(first_cat, on="order_id", how="left")
         .merge(pay_agg, on="order_id", how="left")
         .merge(main_pay, on="order_id", how="left")
         .merge(rev_agg, on="order_id", how="left"))
    o["purchase_ts"] = o["order_purchase_timestamp"]
    o["purchase_date"] = o["purchase_ts"].dt.normalize()
    o["purchase_month"] = o["purchase_ts"].dt.to_period("M")
    o["delivered_ts"] = o["order_delivered_customer_date"]
    o["delivery_days"] = (o["delivered_ts"] - o["purchase_ts"]).dt.total_seconds() / 86400
    o["delay_days"] = (o["delivered_ts"] - o["order_estimated_delivery_date"]).dt.total_seconds() / 86400

    bad_status = o["order_status"].isin(["canceled", "unavailable", "created"])
    no_items = o["n_items"].isna()
    no_pay = o["order_value"].isna()
    after_end = o["purchase_ts"] > end
    valid = ~(bad_status | no_items | no_pay | after_end)
    filt = {
        "toplam_siparis": int(len(o)),
        "iptal_ulasilamaz_olusturuldu": int(bad_status.sum()),
        "kalemi_yok": int(no_items.sum()),
        "odemesi_yok": int(no_pay.sum()),
        "bitis_tarihinden_sonra": int(after_end.sum()),
        "gecerli_siparis": int(valid.sum()),
    }
    keep = ["order_id", "customer_unique_id", "customer_state", "order_status", "purchase_ts", "purchase_date",
            "purchase_month", "delivered_ts", "order_value", "n_items", "price_sum", "freight_sum", "n_categories",
            "first_category", "installments", "pay_type", "review_score", "delivery_days", "delay_days"]
    o = o.loc[valid, keep].sort_values(["customer_unique_id", "purchase_ts"]).reset_index(drop=True)
    it = it.merge(o[["order_id", "customer_unique_id", "purchase_date"]], on="order_id", how="inner")

    cust = build_customers(o, snapshot)
    return o, it, cust, filt


def build_customers(o: pd.DataFrame, snapshot: pd.Timestamp = config.SNAPSHOT) -> pd.DataFrame:
    """Müşteri düzeyinde birleştirme. F = farklı alışveriş günü (aynı gün ek sipariş = sepet bölünmesi)."""
    o = o.sort_values(["customer_unique_id", "purchase_ts"])
    g = o.groupby("customer_unique_id")
    cust = g.agg(
        first_date=("purchase_date", "min"),
        last_date=("purchase_date", "max"),
        n_orders=("order_id", "count"),
        n_days=("purchase_date", "nunique"),
        monetary=("order_value", "sum"),
        state=("customer_state", "first"),
    )
    first = o.drop_duplicates("customer_unique_id").set_index("customer_unique_id")  # o zamana göre sıralı
    cust["first_order_id"] = first["order_id"]
    cust["first_category"] = first["first_category"].fillna("unknown")
    later = o.merge(cust[["first_date"]], left_on="customer_unique_id", right_index=True)
    later = later[later["purchase_date"] > later["first_date"]]
    cust["second_date"] = later.groupby("customer_unique_id")["purchase_date"].min()
    cust["gap_days"] = (cust["second_date"] - cust["first_date"]).dt.days
    cust["recency_days"] = (snapshot - cust["last_date"]).dt.days
    cust["first_month"] = cust["first_date"].dt.to_period("M")
    return cust


# ------------------------------------------------------------------ ara dosyalar (panel bunları okur)
def save_processed(o, it, cust, out_dir: Path | str = config.PROCESSED_DIR) -> None:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    o.drop(columns=["purchase_month"]).to_csv(out_dir / "siparisler.csv.gz", index=False)
    it.to_csv(out_dir / "kalemler.csv.gz", index=False)
    cust.drop(columns=["first_month"]).to_csv(out_dir / "musteriler.csv.gz")


def processed_available(out_dir: Path | str = config.PROCESSED_DIR) -> bool:
    out_dir = Path(out_dir)
    return all((out_dir / f).is_file() for f in ["siparisler.csv.gz", "kalemler.csv.gz", "musteriler.csv.gz"])


def load_processed(out_dir: Path | str = config.PROCESSED_DIR):
    out_dir = Path(out_dir)
    o = pd.read_csv(out_dir / "siparisler.csv.gz", parse_dates=["purchase_ts", "purchase_date", "delivered_ts"])
    o["purchase_month"] = o["purchase_ts"].dt.to_period("M")
    it = pd.read_csv(out_dir / "kalemler.csv.gz", parse_dates=["purchase_date"])
    cust = pd.read_csv(out_dir / "musteriler.csv.gz", index_col="customer_unique_id",
                       parse_dates=["first_date", "last_date", "second_date"])
    cust["first_month"] = cust["first_date"].dt.to_period("M")
    return o, it, cust


def month_index(p: pd.Series) -> pd.Series:
    """Period[M] serisini tam sayı ay sırasına çevirir (yıl*12+ay); pandas sürümlerinden bağımsız."""
    return p.dt.year * 12 + p.dt.month


def wilson(k: float, n: float, z: float = 1.96) -> tuple[float, float]:
    """Bir oran için Wilson güven aralığı (0-1 ölçeğinde)."""
    if n == 0:
        return (np.nan, np.nan)
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (float(c - h), float(c + h))
