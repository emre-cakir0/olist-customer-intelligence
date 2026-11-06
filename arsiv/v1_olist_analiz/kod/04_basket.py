"""Adım 4 - Sepet analizi (kategori düzeyinde birliktelik kuralları).

Kullanım: python3 -I 04_basket.py <cikti_klasoru>

mlxtend kurulamadığı için destek (support), güven (confidence) ve lift pandas ile doğrudan hesaplanır.
Sepet = tek sipariş. Kalem yerine ürün kategorisi kullanılır (ürün düzeyi çok seyrek).
Ek olarak müşteri düzeyinde (farklı siparişlerde) kategori geçişlerine bakılır.
"""
import json
import os
import sys
from collections import Counter
from itertools import combinations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

out = sys.argv[1]
MIN_PAIR = 10  # bir çiftin listeye girmesi için asgari birlikte görülme sayısı

o = pd.read_pickle(os.path.join(out, "orders.pkl"))
it = pd.read_pickle(os.path.join(out, "items.pkl"))
keyf = os.path.join(out, "key_numbers.json")
key = json.load(open(keyf))

# ----------------------------------------------------------- sepet yapısı
n_orders = len(o)
sz = o["n_items"].value_counts().sort_index()
single = float((o.n_items == 1).mean() * 100)
multi_item = float((o.n_items >= 2).mean() * 100)
multi_cat = float((o.n_categories >= 2).mean() * 100)
same_cat_multi = float(((o.n_items >= 2) & (o.n_categories == 1)).mean() * 100)
avg_items = float(o["n_items"].mean())
print(f"Sipariş sayısı: {n_orders:,d} | ort. kalem/sipariş: {avg_items:.3f}")
print(f"tek kalemli: {single:.1f}% | ≥2 kalem: {multi_item:.1f}% | ≥2 farklı kategori: {multi_cat:.2f}% "
      f"| ≥2 kalem ama tek kategori: {same_cat_multi:.1f}%")

# çok kalemli siparişler daha değerli mi?
v1 = o.loc[o.n_items == 1, "order_value"].mean()
v2 = o.loc[o.n_items >= 2, "order_value"].mean()
vmc = o.loc[o.n_categories >= 2, "order_value"].mean()
print(f"ort. sipariş değeri: tek kalem R${v1:.0f} | çok kalem R${v2:.0f} | çok kategori R${vmc:.0f}")

# ----------------------------------------------------------- sipariş içi kategori birlikteliği
# kategorisi bilinmeyen ürünler ("unknown") çift analizinden çıkarılır: iş yorumu taşımaz
baskets = it[it["category_en"] != "unknown"].groupby("order_id")["category_en"].agg(lambda s: sorted(set(s)))
cat_orders = Counter()           # kategori başına sipariş sayısı (tüm siparişler)
for cs in baskets:
    cat_orders.update(cs)
multi = baskets[baskets.apply(len) >= 2]
print(f"\n≥2 (bilinen) kategorili sipariş: {len(multi):,d} (tüm siparişlerin {len(multi)/n_orders:.2%}'i) | 'unknown' çıkarıldı")

pair_cnt = Counter()
cat_multi = Counter()            # kategori başına ÇOK KATEGORİLİ sipariş sayısı
for cs in multi:
    pair_cnt.update(combinations(cs, 2))
    cat_multi.update(cs)
nm = len(multi)
rows = []
for (a, b), n_ab in pair_cnt.items():
    if n_ab < MIN_PAIR:
        continue
    na, nb = cat_orders[a], cat_orders[b]
    rows.append({
        "kategori_A": a, "kategori_B": b, "birlikte_siparis": n_ab,
        "destek_tum_siparis_%": n_ab / n_orders * 100,
        "guven_A->B_%": n_ab / na * 100,
        "guven_B->A_%": n_ab / nb * 100,
        # lift: çok kategorili sepetler evreninde. Tüm siparişlere göre hesaplamak yanıltıcı olur,
        # çünkü siparişlerin %99,2'si zaten tek kategorili ve neredeyse her çift "beklenenden az" görünür.
        "lift_cok_kategorili": (n_ab / nm) / ((cat_multi[a] / nm) * (cat_multi[b] / nm)),
        "A_siparis": na, "B_siparis": nb,
    })
pairs = pd.DataFrame(rows).sort_values("birlikte_siparis", ascending=False)
pairs.round(3).to_csv(os.path.join(out, "sepet_ciftleri.csv"), index=False, encoding="utf-8-sig")
pd.set_option("display.width", 220)
print(f"\n{MIN_PAIR}+ kez birlikte görülen kategori çifti: {len(pairs)}")
print("\n== En sık birlikte alınan çiftler (adede göre) ==")
print(pairs.head(14).round(2).to_string(index=False))
print("\n== En yüksek lift (çok kategorili sepetler evreninde, ≥%d birlikte sipariş) ==" % MIN_PAIR)
print(pairs.sort_values("lift_cok_kategorili", ascending=False).head(10).round(2).to_string(index=False))

# kategori başına "yan satış" potansiyeli: o kategoriyi içeren siparişlerin kaçında başka kategori var
cross = {}
for cs in baskets:
    if len(cs) >= 2:
        for c in cs:
            cross[c] = cross.get(c, 0) + 1
cx = pd.DataFrame({"siparis": pd.Series(cat_orders), "cok_kategorili": pd.Series(cross)}).fillna(0)
cx["cok_kategorili_%"] = cx["cok_kategorili"] / cx["siparis"] * 100
cx = cx[cx.siparis >= 1500].sort_values("cok_kategorili_%", ascending=False)
print("\n== Kategoriyi içeren siparişlerde başka kategoriyle birlikte alınma payı (≥1500 sipariş) ==")
print(cx.head(8).round(2).to_string())
print("...")
print(cx.tail(4).round(2).to_string())

# ----------------------------------------------------------- aynı kategoride çoklu alım
# tek kategorili çok kalemli siparişler: hangi kategorilerde sepet büyüklüğü yüksek
same = it.groupby("order_id").agg(n=("product_id", "size"), nc=("category_en", "nunique"),
                                  cat=("category_en", "first"))
same_multi = same[(same.n >= 2) & (same.nc == 1)]
by_cat = (same.groupby("cat").agg(siparis=("n", "size"), ort_kalem=("n", "mean"),
                                  cok_kalemli_pay=("n", lambda s: (s >= 2).mean() * 100)))
by_cat = by_cat[by_cat.siparis >= 1500].sort_values("cok_kalemli_pay", ascending=False)
print("\n== Aynı siparişte ≥2 kalem payı en yüksek kategoriler (≥1500 sipariş) ==")
print(by_cat.head(8).round(2).to_string())
print("...")
print(by_cat.tail(3).round(2).to_string())
by_cat.round(2).to_csv(os.path.join(out, "sepet_buyuklugu_kategori.csv"), encoding="utf-8-sig")

# ----------------------------------------------------------- müşteri düzeyinde: farklı siparişlerde kategori geçişi
cust_ord = o[["order_id", "customer_unique_id", "purchase_date"]].merge(
    it[["order_id", "category_en"]].drop_duplicates(), on="order_id")
rep_cust = cust_ord.groupby("customer_unique_id")["purchase_date"].nunique()
rep_cust = rep_cust[rep_cust >= 2].index
sub = cust_ord[cust_ord.customer_unique_id.isin(rep_cust)]
cat_sets = sub.groupby("customer_unique_id")["category_en"].agg(lambda s: sorted(set(s)))
n_rep = len(cat_sets)
same_only = float((cat_sets.apply(len) == 1).mean() * 100)
print(f"\nTekrar alan müşteri: {n_rep:,d} | yalnızca tek kategoriden alanlar: {same_only:.1f}%")
rep_cat_cnt = sub.drop_duplicates(["customer_unique_id", "category_en", "purchase_date"]).groupby("category_en").size()
# ilk alım kategorisi -> tekrar alımda aynı kategoriye dönüş
first_cat = (cust_ord.sort_values("purchase_date").drop_duplicates("customer_unique_id")
             .set_index("customer_unique_id")["category_en"])
sub2 = cust_ord[cust_ord.customer_unique_id.isin(rep_cust)].merge(
    first_cat.rename("first_cat"), left_on="customer_unique_id", right_index=True)
later = sub2.merge(o[["order_id", "purchase_date"]].rename(columns={"purchase_date": "pd2"}), on="order_id")
fd = o.groupby("customer_unique_id")["purchase_date"].min().rename("fd")
later = later.merge(fd, left_on="customer_unique_id", right_index=True)
later = later[later.pd2 > later.fd]
back_same = float(later.groupby("customer_unique_id").apply(lambda g: (g.category_en == g.first_cat).any()).mean() * 100)
print(f"Tekrar alanların ilk alım kategorisine geri dönme payı: {back_same:.1f}%")

# ----------------------------------------------------------- grafik: en sık birlikte alınan çiftler (+ lift)
top = pairs.head(10).iloc[::-1]
labels = [f"{a} + {b}" for a, b in zip(top.kategori_A, top.kategori_B)]
fig, ax = plt.subplots(figsize=(10, 5.2))
ax.barh(labels, top["birlikte_siparis"], color="#1f5f8b")
for y_, n_, l_ in zip(range(len(top)), top["birlikte_siparis"], top["lift_cok_kategorili"]):
    ax.text(n_ + 0.8, y_, f"{n_}  (lift {l_:.1f})".replace(".", ","), va="center", fontsize=8)
ax.set_xlabel("Birlikte alınan sipariş sayısı (tüm veri, 98.197 sipariş içinde)")
ax.set_xlim(0, top["birlikte_siparis"].max() * 1.25)
ax.set_title("En sık birlikte alınan kategori çiftleri (lift: çok kategorili sepetlere göre)", fontsize=10.5)
for s_ in ["top", "right"]:
    ax.spines[s_].set_visible(False)
fig.tight_layout()
fig.savefig(os.path.join(out, "fig_sepet_ciftleri.png"), dpi=160)
plt.close(fig)

key["basket"] = {
    "orders": int(n_orders),
    "avg_items_per_order": avg_items,
    "single_item_pct": single,
    "multi_item_pct": multi_item,
    "multi_category_pct": multi_cat,
    "multi_item_same_category_pct": same_cat_multi,
    "n_multi_category_orders": int(len(multi)),
    "min_pair": MIN_PAIR,
    "aov_single": float(v1), "aov_multi_item": float(v2), "aov_multi_category": float(vmc),
    "pairs_over_min": int(len(pairs)),
    "top_pairs_by_count": json.loads(pairs.head(8).round(3).to_json(orient="records", force_ascii=False)),
    "top_pairs_by_lift": json.loads(pairs.sort_values("lift_cok_kategorili", ascending=False).head(8).round(3).to_json(orient="records", force_ascii=False)),
    "repeaters": int(n_rep),
    "repeaters_single_category_pct": same_only,
    "repeaters_back_to_first_category_pct": back_same,
}
json.dump(key, open(keyf, "w"), ensure_ascii=False, indent=2, default=float)
print("\nkaydedildi.")
