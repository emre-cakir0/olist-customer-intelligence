"""Sepet analizi (kategori düzeyinde birliktelik).

Sepet = tek sipariş; ürün yerine ürün kategorisi kullanılır (ürün düzeyinde eşleşme çok seyrek).
"unknown" kategorisi çift analizinden çıkarılır.

Raporlanan ölçüler (A ve B iki kategori, N tüm siparişler):
  destek      = A ve B'yi birlikte içeren sipariş / N
  güven A→B   = A ve B'yi birlikte içeren sipariş / A'yı içeren sipariş   (%95 Wilson aralığıyla)
  lift        = destek / (P(A) · P(B))  — tüm siparişlere göre
  lift (çok kategorili) = aynı oran, yalnızca ≥2 kategorili sepetler evreninde
Siparişlerin %99'u tek kategorili olduğundan tüm siparişlere göre lift neredeyse her çift için 1'in altındadır;
çok kategorili evrendeki lift, "iki kategori birlikte alındığında hangileri yan yana geliyor" sorusunu yanıtlar.
"""
from __future__ import annotations

from collections import Counter
from itertools import combinations

import numpy as np
import pandas as pd

from . import config
from .data import wilson


def basket_structure(orders: pd.DataFrame) -> dict[str, float]:
    o = orders
    return {
        "siparis": int(len(o)),
        "ort_kalem": float(o["n_items"].mean()),
        "tek_kalemli_%": float((o["n_items"] == 1).mean() * 100),
        "cok_kalemli_%": float((o["n_items"] >= 2).mean() * 100),
        "cok_kalemli_tek_kategori_%": float(((o["n_items"] >= 2) & (o["n_categories"] == 1)).mean() * 100),
        "cok_kategorili_%": float((o["n_categories"] >= 2).mean() * 100),
        "ort_tutar_tek_kalem": float(o.loc[o["n_items"] == 1, "order_value"].mean()),
        "ort_tutar_cok_kalem": float(o.loc[o["n_items"] >= 2, "order_value"].mean()),
        "ort_tutar_cok_kategori": float(o.loc[o["n_categories"] >= 2, "order_value"].mean()),
    }


def category_pairs(items: pd.DataFrame, n_orders: int, min_pair: int = config.MIN_PAIR_ORDERS,
                   low_sample: int = config.LOW_SAMPLE_PAIR):
    """Kategori çiftleri için destek, güven ve lift. Döndürür: (çift_tablosu, çok_kategorili_sipariş_sayısı)."""
    baskets = (items[items["category_en"] != "unknown"].groupby("order_id")["category_en"]
               .agg(lambda s: tuple(sorted(set(s)))))
    cat_orders = Counter()
    for cs in baskets:
        cat_orders.update(cs)
    multi = baskets[baskets.apply(len) >= 2]
    nm = len(multi)
    pair_cnt, cat_multi = Counter(), Counter()
    for cs in multi:
        pair_cnt.update(combinations(cs, 2))
        cat_multi.update(cs)
    rows = []
    for (a, b), n_ab in pair_cnt.items():
        if n_ab < min_pair:
            continue
        na, nb = cat_orders[a], cat_orders[b]
        ab_lo, ab_hi = wilson(n_ab, na)
        ba_lo, ba_hi = wilson(n_ab, nb)
        rows.append({
            "kategori_A": a, "kategori_B": b, "birlikte_siparis": n_ab,
            "A_siparis": na, "B_siparis": nb,
            "destek_%": n_ab / n_orders * 100,
            "guven_A_B_%": n_ab / na * 100, "guven_A_B_ga_alt_%": ab_lo * 100, "guven_A_B_ga_ust_%": ab_hi * 100,
            "guven_B_A_%": n_ab / nb * 100, "guven_B_A_ga_alt_%": ba_lo * 100, "guven_B_A_ga_ust_%": ba_hi * 100,
            "lift_tum_siparis": (n_ab / n_orders) / ((na / n_orders) * (nb / n_orders)),
            "lift_cok_kategorili": (n_ab / nm) / ((cat_multi[a] / nm) * (cat_multi[b] / nm)),
            "dusuk_orneklem": bool(n_ab < low_sample),
        })
    cols = ["kategori_A", "kategori_B", "birlikte_siparis", "A_siparis", "B_siparis", "destek_%", "guven_A_B_%",
            "guven_A_B_ga_alt_%", "guven_A_B_ga_ust_%", "guven_B_A_%", "guven_B_A_ga_alt_%", "guven_B_A_ga_ust_%",
            "lift_tum_siparis", "lift_cok_kategorili", "dusuk_orneklem"]
    pairs = pd.DataFrame(rows, columns=cols).sort_values(["birlikte_siparis", "kategori_A"],
                                                          ascending=[False, True]).reset_index(drop=True)
    return pairs, nm


def multi_item_by_category(items: pd.DataFrame, min_orders: int = 1500) -> pd.DataFrame:
    """İlk kalemin kategorisine göre, aynı siparişte ≥2 kalem bulunan siparişlerin payı."""
    s = (items.sort_values(["order_id", "order_item_id"])
         .groupby("order_id").agg(n=("product_id", "size"), kategori=("category_en", "first")))
    t = s.groupby("kategori").agg(siparis=("n", "size"), ort_kalem=("n", "mean"),
                                  cok_kalemli_pay_=("n", lambda x: (x >= 2).mean() * 100))
    t = t.rename(columns={"cok_kalemli_pay_": "cok_kalemli_pay_%"})
    return t[t["siparis"] >= min_orders].sort_values("cok_kalemli_pay_%", ascending=False)


def repeat_category_behaviour(orders: pd.DataFrame, items: pd.DataFrame, customers: pd.DataFrame) -> dict:
    """Tekrar alanlar (≥2 alışveriş günü) tek kategoride mi kalıyor, ilk kategoriye dönüyor mu?"""
    rep = customers.index[customers["n_days"] >= 2]
    co = (items[items["customer_unique_id"].isin(rep)][["customer_unique_id", "purchase_date", "category_en"]]
          .drop_duplicates())
    single = co.groupby("customer_unique_id")["category_en"].nunique().eq(1).mean() * 100
    co = co.merge(customers[["first_date", "first_category"]], left_on="customer_unique_id", right_index=True)
    later = co[co["purchase_date"] > co["first_date"]]
    back = later.assign(same=later["category_en"] == later["first_category"]).groupby("customer_unique_id")["same"].any()
    return {"tekrar_alan": int(len(rep)), "tek_kategoride_kalan_%": float(single),
            "ilk_kategoriye_donen_%": float(back.mean() * 100)}
