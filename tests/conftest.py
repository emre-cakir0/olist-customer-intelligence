"""Testler için küçük, elle kurulmuş bir Olist benzeri veri seti.

Gerçek veriye ihtiyaç duymayan birim testleri bu sentetik veriyi kullanır; böylece tanımlar
(tekrar alım, kohort, churn penceresi, sepet ölçüleri) bilinen sonuçlarla sınanır.
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _order(oid, cid, ts, status="delivered", delivered_after_days=5.0, estimated_after_days=10.0):
    ts = pd.Timestamp(ts)
    return {
        "order_id": oid, "customer_id": cid, "order_status": status, "order_purchase_timestamp": ts,
        "order_approved_at": ts, "order_delivered_carrier_date": ts,
        "order_delivered_customer_date": ts + pd.Timedelta(days=delivered_after_days)
        if delivered_after_days is not None else pd.NaT,
        "order_estimated_delivery_date": ts + pd.Timedelta(days=estimated_after_days),
    }


@pytest.fixture
def toy_raw():
    """Müşteriler:
      A: 2017-01-10 ilk sipariş, aynı gün ikinci sipariş (sepet bölünmesi), 2017-03-05 tekrar alım
      B: 2017-01-20 tek sipariş
      C: 2017-02-03 ilk sipariş, 2017-12-01 tekrar alım (teslimattan 296 gün sonra)
      D: 2017-02-15 iptal edilmiş sipariş (geçersiz) + 2017-02-16 geçerli sipariş
      E: 2018-09-05 sipariş (bitiş tarihinden sonra, geçersiz)
    """
    orders = pd.DataFrame([
        _order("o1", "cA1", "2017-01-10 10:00"),
        _order("o2", "cA2", "2017-01-10 15:00"),
        _order("o3", "cA3", "2017-03-05 09:00"),
        _order("o4", "cB1", "2017-01-20 12:00", delivered_after_days=25),
        _order("o5", "cC1", "2017-02-03 08:00"),
        _order("o6", "cC2", "2017-12-01 08:00"),
        _order("o7", "cD1", "2017-02-15 08:00", status="canceled"),
        _order("o8", "cD2", "2017-02-16 08:00"),
        _order("o9", "cE1", "2018-09-05 08:00"),
    ])
    customers = pd.DataFrame({
        "customer_id": ["cA1", "cA2", "cA3", "cB1", "cC1", "cC2", "cD1", "cD2", "cE1"],
        "customer_unique_id": ["A", "A", "A", "B", "C", "C", "D", "D", "E"],
        "customer_state": ["SP", "SP", "SP", "RJ", "MG", "MG", "SP", "SP", "SP"],
    })
    items = pd.DataFrame([
        ("o1", 1, "p_bed", 100.0, 10.0), ("o1", 2, "p_fur", 50.0, 5.0),
        ("o2", 1, "p_bed", 40.0, 4.0),
        ("o3", 1, "p_toy", 30.0, 3.0),
        ("o4", 1, "p_bed", 80.0, 8.0), ("o4", 2, "p_fur", 20.0, 2.0),
        ("o5", 1, "p_toy", 60.0, 6.0),
        ("o6", 1, "p_fur", 70.0, 7.0),
        ("o7", 1, "p_toy", 10.0, 1.0),
        ("o8", 1, "p_toy", 15.0, 1.5),
        ("o9", 1, "p_toy", 25.0, 2.5),
    ], columns=["order_id", "order_item_id", "product_id", "price", "freight_value"])
    pay_rows = []
    for oid, g in items.groupby("order_id"):
        pay_rows.append({"order_id": oid, "payment_sequential": 1, "payment_type": "credit_card",
                         "payment_installments": 1, "payment_value": float((g.price + g.freight_value).sum())})
    payments = pd.DataFrame(pay_rows)
    reviews = pd.DataFrame({"order_id": ["o1", "o3", "o4", "o5"], "review_score": [5, 4, 1, 3]})
    products = pd.DataFrame({"product_id": ["p_bed", "p_fur", "p_toy"],
                             "product_category_name": ["cama_mesa_banho", "moveis_decoracao", "brinquedos"]})
    translation = pd.DataFrame({"product_category_name": ["cama_mesa_banho", "moveis_decoracao", "brinquedos"],
                                "category_en": ["bed_bath_table", "furniture_decor", "toys"]})
    return {"orders": orders, "customers": customers, "items": items, "payments": payments, "reviews": reviews,
            "products": products, "translation": translation}


@pytest.fixture
def toy_tables(toy_raw):
    from olist_ci import data
    return data.build_tables(toy_raw)
