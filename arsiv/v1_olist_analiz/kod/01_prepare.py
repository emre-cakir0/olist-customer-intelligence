"""Adım 1 - Veri hazırlığı.

Kullanım: python3 -I 01_prepare.py <ham_csv_klasoru> <cikti_klasoru>

Ham Olist tablolarını okur, geçerli siparişleri seçer ve üç tablo üretir:
  orders.pkl     sipariş düzeyi (değer, kalem, ödeme, yorum, teslimat)
  items.pkl      kalem düzeyi (kategori İngilizce adıyla)
  customers.pkl  müşteri düzeyi (customer_unique_id bazında R, F, M ham değerleri)
"""
import json
import os
import sys

import numpy as np
import pandas as pd

raw, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
P = lambda f: os.path.join(raw, f)

# Analiz penceresi: son tam ay 2018-08. Eylül/Ekim 2018'de yalnızca birkaç sipariş var.
END = pd.Timestamp("2018-08-31 23:59:59")
SNAPSHOT = pd.Timestamp("2018-09-01")

ts_cols = [
    "order_purchase_timestamp",
    "order_approved_at",
    "order_delivered_carrier_date",
    "order_delivered_customer_date",
    "order_estimated_delivery_date",
]
orders = pd.read_csv(P("olist_orders_dataset.csv"), parse_dates=ts_cols)
customers = pd.read_csv(
    P("olist_customers_dataset.csv"),
    usecols=["customer_id", "customer_unique_id", "customer_state"],
)
items = pd.read_csv(
    P("olist_order_items_dataset.csv"),
    usecols=["order_id", "order_item_id", "product_id", "price", "freight_value"],
)
pay = pd.read_csv(P("olist_order_payments_dataset.csv"))
rev = pd.read_csv(P("olist_order_reviews_dataset.csv"), usecols=["order_id", "review_score"])
prod = pd.read_csv(P("olist_products_dataset.csv"), usecols=["product_id", "product_category_name"])
tr = pd.read_csv(P("product_category_name_translation.csv"))
tr.columns = ["product_category_name", "category_en"]  # BOM'lu sütun adına karşı konumla adlandır

print("== Ham tablo boyutları ==")
for name, df in [("orders", orders), ("customers", customers), ("items", items),
                 ("payments", pay), ("reviews", rev), ("products", prod)]:
    print(f"{name:10s} {len(df):>9,d}")
print("\n== Sipariş durumları ==")
print(orders.order_status.value_counts().to_string())

# ---- kalem düzeyi + kategori -------------------------------------------------
prod = prod.merge(tr, on="product_category_name", how="left")
prod["category_en"] = prod["category_en"].fillna(prod["product_category_name"]).fillna("unknown")
it = items.merge(prod[["product_id", "category_en"]], on="product_id", how="left")
it["category_en"] = it["category_en"].fillna("unknown")

# ---- sipariş düzeyi ----------------------------------------------------------
agg_items = it.groupby("order_id").agg(
    n_items=("order_item_id", "count"),
    price_sum=("price", "sum"),
    freight_sum=("freight_value", "sum"),
    n_categories=("category_en", "nunique"),
)
pay_agg = pay.groupby("order_id").agg(
    order_value=("payment_value", "sum"),
    installments=("payment_installments", "max"),
)
main_pay = (
    pay.sort_values("payment_value", ascending=False)
    .drop_duplicates("order_id")[["order_id", "payment_type"]]
    .rename(columns={"payment_type": "pay_type"})
)
rev_agg = rev.groupby("order_id")["review_score"].mean().rename("review_score")

o = (
    orders.merge(customers, on="customer_id", how="left")
    .merge(agg_items, on="order_id", how="left")
    .merge(pay_agg, on="order_id", how="left")
    .merge(main_pay, on="order_id", how="left")
    .merge(rev_agg, on="order_id", how="left")
)
o["purchase_ts"] = o["order_purchase_timestamp"]
o["purchase_date"] = o["purchase_ts"].dt.normalize()
o["purchase_month"] = o["purchase_ts"].dt.to_period("M")
o["delivery_days"] = (o["order_delivered_customer_date"] - o["purchase_ts"]).dt.total_seconds() / 86400
o["delay_days"] = (o["order_delivered_customer_date"] - o["order_estimated_delivery_date"]).dt.total_seconds() / 86400
o["is_late"] = (o["delay_days"] > 0).where(o["delay_days"].notna())

# ---- geçerli sipariş filtresi ------------------------------------------------
n0 = len(o)
bad_status = o["order_status"].isin(["canceled", "unavailable", "created"])
no_items = o["n_items"].isna()
no_pay = o["order_value"].isna()
after_end = o["purchase_ts"] > END
valid = ~(bad_status | no_items | no_pay | after_end)
print("\n== Geçerli sipariş filtresi ==")
print(f"toplam sipariş            : {n0:,d}")
print(f"iptal/ulaşılamaz/created  : {bad_status.sum():,d}")
print(f"kalemi olmayan            : {no_items.sum():,d}")
print(f"ödemesi olmayan           : {no_pay.sum():,d}")
print(f"2018-08 sonrası           : {after_end.sum():,d}")
print(f"geçerli                   : {valid.sum():,d}")
o = o[valid].copy()

keep = [
    "order_id", "customer_unique_id", "customer_state", "order_status", "purchase_ts",
    "purchase_date", "purchase_month", "order_value", "n_items", "price_sum", "freight_sum",
    "n_categories", "installments", "pay_type", "review_score", "delivery_days", "delay_days",
    "is_late",
]
o = o[keep].sort_values(["customer_unique_id", "purchase_ts"]).reset_index(drop=True)
it = it.merge(o[["order_id", "customer_unique_id", "purchase_month"]], on="order_id", how="inner")

# ---- müşteri düzeyi ----------------------------------------------------------
g = o.groupby("customer_unique_id")
cust = g.agg(
    first_date=("purchase_date", "min"),
    last_date=("purchase_date", "max"),
    n_orders=("order_id", "count"),
    n_days=("purchase_date", "nunique"),   # farklı alışveriş günü sayısı (F için kullanılacak)
    monetary=("order_value", "sum"),
    state=("customer_state", "first"),
)
cust["recency_days"] = (SNAPSHOT - cust["last_date"]).dt.days
cust["first_month"] = cust["first_date"].dt.to_period("M")

o.to_pickle(os.path.join(out, "orders.pkl"))
it.to_pickle(os.path.join(out, "items.pkl"))
cust.to_pickle(os.path.join(out, "customers.pkl"))

# ---- keşif istatistikleri ----------------------------------------------------
print("\n== Keşif ==")
print("tarih aralığı:", o["purchase_ts"].min(), "->", o["purchase_ts"].max())
print("benzersiz müşteri:", f"{len(cust):,d}", "| sipariş/müşteri ort.:", round(len(o) / len(cust), 3))
print("toplam ciro (R$):", f"{o['order_value'].sum():,.0f}", "| ort. sipariş değeri:", round(o["order_value"].mean(), 2))
print("\nfarklı alışveriş günü (F) dağılımı:")
vc = cust["n_days"].value_counts().sort_index()
for k, v in vc.items():
    print(f"  F={k}: {v:,d}  ({v/len(cust):.2%})")
print(f"\nsipariş sayısı>1 olan müşteri : {(cust.n_orders>1).sum():,d} ({(cust.n_orders>1).mean():.2%})")
print(f"gün sayısı>1 olan müşteri     : {(cust.n_days>1).sum():,d} ({(cust.n_days>1).mean():.2%})")
print("\nsipariş başına kalem:")
print(o["n_items"].value_counts().sort_index().head(6).to_string())
print(f"tek kalemli sipariş payı: {(o.n_items==1).mean():.1%} | ≥2 farklı kategori: {(o.n_categories>=2).mean():.1%}")
print("\naylık geçerli sipariş sayısı:")
print(o.groupby("purchase_month").size().to_string())
print("\neksik oranlar: review", f"{o.review_score.isna().mean():.1%}",
      "| teslim süresi", f"{o.delivery_days.isna().mean():.1%}")
