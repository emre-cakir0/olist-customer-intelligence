"""RFM segmentasyonu.

RFM tarihi: config.SNAPSHOT (1 Eylül 2018, son geçerli siparişten sonraki gün).
  R (recency)   = RFM tarihi ile son alışveriş günü arasındaki gün
  F (frequency) = farklı alışveriş günü sayısı
  M (monetary)  = toplam ödeme (kargo dahil, R$)
Puanlama: R ve M tüm müşteriler üzerinde beşe eşit dilime (quintile) bölünür; R puanı 5 = en yakın,
M puanı 5 = en yüksek harcama. F'nin %97,8'i 1 olduğundan beşli dilim anlamsızdır; F yalnızca 1 / 2+ diye ayrılır.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config

SEGMENT_ORDER = ["Şampiyonlar", "Uyuyan sadıklar", "Yeni - yüksek sepet", "Yeni - standart",
                 "Soğuyanlar", "Kayıp - yüksek değerli", "Kayıp - standart"]

# Kurallar sırayla uygulanır; müşteri ilk uyan segmente girer.
SEGMENT_RULES = {
    "Şampiyonlar": "F ≥ 2 ve R puanı ≥ 4",
    "Uyuyan sadıklar": "F ≥ 2 ve R puanı ≤ 3",
    "Yeni - yüksek sepet": "F = 1, R puanı ≥ 4, M puanı ≥ 4",
    "Yeni - standart": "F = 1, R puanı ≥ 4, M puanı ≤ 3",
    "Soğuyanlar": "F = 1, R puanı = 3",
    "Kayıp - yüksek değerli": "F = 1, R puanı ≤ 2, M puanı ≥ 4",
    "Kayıp - standart": "F = 1, R puanı ≤ 2, M puanı ≤ 3",
}


def score_rfm(customers: pd.DataFrame):
    """R, F, M değerlerini ve puanlarını ekler. Döndürür: (tablo, kesim_noktalari)."""
    c = customers.copy()
    c["R"] = c["recency_days"]
    c["F"] = c["n_days"]
    c["M"] = c["monetary"]
    r_bins = pd.qcut(c["R"], 5, labels=False, retbins=True, duplicates="drop")
    m_bins = pd.qcut(c["M"], 5, labels=False, retbins=True, duplicates="drop")
    c["r_score"] = (5 - r_bins[0]).astype(int)   # en küçük recency dilimi = 5
    c["m_score"] = (1 + m_bins[0]).astype(int)
    cuts = {"R_sinirlari_gun": [float(x) for x in r_bins[1][1:-1]],
            "M_sinirlari_R$": [float(x) for x in m_bins[1][1:-1]]}
    return c, cuts


def assign_segments(c: pd.DataFrame) -> pd.Series:
    r, m, F = c["r_score"], c["m_score"], c["F"]
    conds = [(F >= 2) & (r >= 4), (F >= 2), (r >= 4) & (m >= 4), (r >= 4), (r == 3), (r <= 2) & (m >= 4)]
    return pd.Series(np.select(conds, SEGMENT_ORDER[:6], default=SEGMENT_ORDER[6]), index=c.index, name="segment")


def segment_summary(c: pd.DataFrame, orders: pd.DataFrame) -> pd.DataFrame:
    """Segment başına müşteri, ciro, ortalama harcama, son alımdan geçen gün, yorum puanı."""
    rv = orders.groupby("customer_unique_id")["review_score"].mean()
    d = c.assign(avg_review=rv.reindex(c.index), aov=c["M"] / c["n_orders"])
    seg = d.groupby("segment").agg(
        musteri=("M", "size"), ciro=("M", "sum"), ort_harcama=("M", "mean"),
        ort_siparis_degeri=("aov", "mean"), ort_recency_gun=("R", "mean"),
        ort_alisveris_gunu=("F", "mean"), ort_yorum_puani=("avg_review", "mean"),
    ).reindex([s for s in SEGMENT_ORDER if s in set(d["segment"])])
    seg["musteri_payi_%"] = seg["musteri"] / seg["musteri"].sum() * 100
    seg["ciro_payi_%"] = seg["ciro"] / seg["ciro"].sum() * 100
    seg.insert(0, "kural", [SEGMENT_RULES[s] for s in seg.index])
    seg.index.name = "segment"
    return seg[["kural", "musteri", "musteri_payi_%", "ciro", "ciro_payi_%", "ort_harcama", "ort_siparis_degeri",
                "ort_recency_gun", "ort_alisveris_gunu", "ort_yorum_puani"]]


def concentration(c: pd.DataFrame) -> dict[str, float]:
    srt = c["M"].sort_values(ascending=False)
    tot = srt.sum()
    rep = c["F"] >= 2
    return {
        "ilk_%10_ciro_payi": float(srt.head(int(len(srt) * .1)).sum() / tot * 100),
        "ilk_%20_ciro_payi": float(srt.head(int(len(srt) * .2)).sum() / tot * 100),
        "tekrar_alan_musteri_payi_%": float(rep.mean() * 100),
        "tekrar_alan_ciro_payi_%": float(c.loc[rep, "M"].sum() / tot * 100),
        "tek_alimli_ort_harcama": float(c.loc[~rep, "M"].mean()),
        "tekrar_alan_ort_harcama": float(c.loc[rep, "M"].mean()),
    }
