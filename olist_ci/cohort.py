"""Kohort analizi.

Kohort = müşterinin ilk sipariş ayı. Tekrar alım = ilk alışveriş gününden SONRAKİ bir günde verilen sipariş
(aynı gün verilen ek siparişler sepet bölünmesi sayılır).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config
from .data import month_index


def retention_matrix(orders: pd.DataFrame, customers: pd.DataFrame,
                     start: pd.Period = config.COHORT_START,
                     last_full_month: pd.Period = config.LAST_FULL_MONTH,
                     max_offset: int = config.COHORT_MAX_OFFSET):
    """Kohort × ay tutunma matrisi.

    Hücre (kohort c, ay k): c kohortundan, c+k ayında yeniden alışveriş yapan müşteri sayısı / kohort büyüklüğü.
    c+k son tam aydan sonraysa hücre gözlenmemiş sayılır (NaN). Yalnızca en az bir gözlenebilir hücresi olan
    kohortlar (start ≤ c < last_full_month) alınır.

    Döndürür: (sayilar, yuzde, kohort_buyuklugu)
    """
    cust = customers[(customers["first_month"] >= start) & (customers["first_month"] < last_full_month)]
    sizes = cust.groupby("first_month").size()
    if sizes.empty:
        empty = pd.DataFrame(columns=range(1, max_offset + 1), dtype=float)
        return empty, empty, sizes
    oo = orders.merge(cust[["first_date", "first_month"]], left_on="customer_unique_id", right_index=True)
    oo = oo[oo["purchase_date"] > oo["first_date"]].copy()
    oo["offset"] = month_index(oo["purchase_month"]) - month_index(oo["first_month"])
    counts = (oo[oo["offset"].between(1, max_offset)]
              .groupby(["first_month", "offset"])["customer_unique_id"].nunique()
              .unstack(fill_value=0)
              .reindex(index=sizes.index, columns=range(1, max_offset + 1), fill_value=0)
              .astype(float))
    last_idx = last_full_month.year * 12 + last_full_month.month
    for cm in counts.index:
        cidx = cm.year * 12 + cm.month
        for k in counts.columns:
            if cidx + k > last_idx:
                counts.loc[cm, k] = np.nan
    pct = counts.div(sizes, axis=0) * 100
    return counts, pct, sizes


def weighted_retention(counts: pd.DataFrame, sizes: pd.Series, ks=(1, 2, 3, 6, 12)) -> dict[int, float]:
    """k. aydaki tutunmanın, o hücreyi gözlenen kohortların büyüklüğüyle ağırlıklı ortalaması (%)."""
    out = {}
    for k in ks:
        if k not in counts.columns:
            continue
        obs = counts[k].notna()
        out[k] = float(counts.loc[obs, k].sum() / sizes[obs].sum() * 100) if obs.any() else np.nan
    return out


def repeat_within(customers: pd.DataFrame, days: int, obs_end: pd.Timestamp = config.OBS_END,
                  start: pd.Period = config.COHORT_START) -> tuple[float, int]:
    """İlk alımdan sonraki `days` gün içinde tekrar alan müşteri payı (%).

    Yalnızca penceresi tamamen gözlenen müşteriler (ilk alım + days ≤ obs_end) sayılır.
    Döndürür: (oran_%, payda)
    """
    elig = customers[(customers["first_month"] >= start)
                     & (customers["first_date"] + pd.Timedelta(days=days) <= obs_end)]
    if len(elig) == 0:
        return np.nan, 0
    return float((elig["gap_days"] <= days).mean() * 100), int(len(elig))


def gap_stats(customers: pd.DataFrame) -> dict[str, float]:
    """Tekrar alanlarda ilk ve ikinci alışveriş günü arasındaki süre."""
    g = customers["gap_days"].dropna()
    return {
        "tekrar_alan": int(len(g)),
        "medyan_gun": float(g.median()),
        "p25_gun": float(g.quantile(.25)),
        "p75_gun": float(g.quantile(.75)),
        "p90_gun": float(g.quantile(.90)),
        **{f"{d}_gun_icinde_%": float((g <= d).mean() * 100) for d in (30, 90, 180, 365)},
    }


def cohort_repeat_table(customers: pd.DataFrame, days=(90, 180), obs_end: pd.Timestamp = config.OBS_END,
                        start: pd.Period = config.COHORT_START,
                        last_full_month: pd.Period = config.LAST_FULL_MONTH) -> pd.DataFrame:
    """Kohort başına N gün içinde tekrar alım. Penceresi kohortun tüm müşterileri için kapanmamışsa boş."""
    rows = []
    cust = customers[(customers["first_month"] >= start) & (customers["first_month"] <= last_full_month)]
    for cm, sub in cust.groupby("first_month"):
        row = {"kohort": str(cm), "musteri": int(len(sub))}
        for n in days:
            full = cm.end_time.normalize() + pd.Timedelta(days=n) <= obs_end
            row[f"tekrar_{n}g_%"] = float((sub["gap_days"] <= n).mean() * 100) if full else np.nan
        rows.append(row)
    return pd.DataFrame(rows)
