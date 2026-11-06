"""Olist yönetici paneli (Streamlit).

Çalıştırma (proje klasöründe, önce `python run_pipeline.py`):
    streamlit run app/panel.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from olist_ci import churn, cohort, config, data, rfm  # noqa: E402

st.set_page_config(page_title="Olist Yönetici Paneli", layout="wide")


def tr(x, nd=1):
    if x is None or pd.isna(x):
        return "—"
    s = f"{x:,.{nd}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


@st.cache_data(show_spinner="Veri yükleniyor...")
def load():
    o, it, cust = data.load_processed()
    return o, it, cust


@st.cache_data
def load_table(name: str) -> pd.DataFrame:
    return pd.read_csv(config.TABLES_DIR / name, encoding="utf-8-sig")


@st.cache_data
def load_results() -> dict:
    with open(config.TABLES_DIR / "sonuclar.json", encoding="utf-8") as f:
        return json.load(f)


# ------------------------------------------------------------------ veri kontrolü
if not data.processed_available() or not (config.TABLES_DIR / "sonuclar.json").is_file():
    st.title("Olist Yönetici Paneli")
    missing = data.missing_raw_files()
    if missing:
        st.error("Ham veri bulunamadı ve analiz çıktıları henüz üretilmedi.")
        st.code(data.raw_missing_message(config.RAW_DIR, missing), language="text")
    else:
        st.warning("Analiz çıktıları bulunamadı. Önce proje klasöründe şu komutu çalıştırın:")
        st.code("python run_pipeline.py", language="powershell")
    st.stop()

o, it, cust = load()
K = load_results()

# ------------------------------------------------------------------ filtreler
st.sidebar.header("Filtreler")
months = sorted(cust["first_month"].astype(str).unique())
m_from, m_to = st.sidebar.select_slider("İlk sipariş ayı (kohort)", options=months,
                                        value=(months[0], months[-1]))
states = sorted(cust["state"].dropna().unique())
sel_states = st.sidebar.multiselect("Eyalet", states, placeholder="Tümü")
segs = [s for s in rfm.SEGMENT_ORDER if s in set(cust["segment"])]
sel_segs = st.sidebar.multiselect("RFM segmenti", segs, placeholder="Tümü")
top_cats = cust["first_category"].value_counts().head(25).index.tolist()
sel_cats = st.sidebar.multiselect("İlk siparişin kategorisi (en büyük 25)", top_cats, placeholder="Tümü")
st.sidebar.caption("Filtreler müşteriye uygulanır: seçilen müşterilerin tüm siparişleri hesaba katılır. "
                   "Sepet, tahmin ve model sonuçları tüm veriye aittir.")

fm = cust["first_month"].astype(str)
mask = (fm >= m_from) & (fm <= m_to)
if sel_states:
    mask &= cust["state"].isin(sel_states)
if sel_segs:
    mask &= cust["segment"].isin(sel_segs)
if sel_cats:
    mask &= cust["first_category"].isin(sel_cats)
c_f = cust[mask]
o_f = o[o["customer_unique_id"].isin(c_f.index)]

st.title("Olist Müşteri ve Satış Analitiği")
st.caption(f"Veri: Olist Brezilya e-ticaret veri seti, geçerli siparişler {K['veri']['ilk_siparis'][:10]} – "
           f"{K['veri']['son_siparis'][:10]}. RFM tarihi {K['tanimlar']['rfm_tarihi']}. "
           f"Seçili müşteri: {tr(len(c_f), 0)} / {tr(len(cust), 0)}.")
if c_f.empty:
    st.warning("Bu filtrelerle müşteri kalmadı. Filtreleri genişletin.")
    st.stop()

tabs = st.tabs(["Genel bakış", "Kohort", "RFM", "Churn", "Sepet", "Tahmin", "Tanımlar"])

# ------------------------------------------------------------------ genel bakış
with tabs[0]:
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Müşteri", tr(len(c_f), 0))
    k2.metric("Ciro", f"R${tr(c_f['monetary'].sum() / 1e6, 2)} mn")
    k3.metric("Ortalama sipariş tutarı", f"R${tr(o_f['order_value'].mean(), 0)}")
    k4.metric("Birden fazla alışveriş günü olan", f"%{tr((c_f['n_days'] >= 2).mean() * 100, 2)}")
    monthly = (o_f[o_f["purchase_date"] >= "2017-01-01"].groupby(o_f["purchase_month"].astype(str))["order_value"]
               .sum().rename("Ciro (R$)"))
    st.subheader("Aylık ciro")
    st.bar_chart(monthly)
    st.caption("Ağustos 2018 eksik ay: veri 22 Ağustos'tan sonra azalıyor.")

# ------------------------------------------------------------------ kohort
with tabs[1]:
    counts, pct, sizes = cohort.retention_matrix(o_f, c_f)
    st.subheader("Aylık tutunma (%): kohorttan o ay yeniden alışveriş yapanların payı")
    if pct.empty:
        st.info("Seçimde gözlenebilir kohort yok.")
    else:
        w = cohort.weighted_retention(counts, sizes)
        cols = st.columns(len(w))
        for col, (k, val) in zip(cols, w.items()):
            col.metric(f"{k}. ay", f"%{tr(val, 2)}")
        show = pct.copy()
        show.index = [f"{i} (n={sizes[i]})" for i in show.index.astype(str)]
        st.dataframe(show.style.format(lambda x: "" if pd.isna(x) else tr(x, 2)).background_gradient(
            cmap="YlGnBu", axis=None), width="stretch")
        st.caption("Kohort = ilk sipariş ayı. Son tam ay 2018-07; boş hücreler henüz gözlenmedi. "
                   "Küçük kohortlarda (n < 500) oranlar oynaktır.")

# ------------------------------------------------------------------ RFM
with tabs[2]:
    seg = rfm.segment_summary(c_f, o_f)
    st.subheader("RFM segmentleri")
    st.bar_chart(seg[["musteri_payi_%", "ciro_payi_%"]].rename(
        columns={"musteri_payi_%": "Müşteri payı (%)", "ciro_payi_%": "Ciro payı (%)"}), horizontal=True)
    st.dataframe(seg.rename(columns={
        "kural": "Kural", "musteri": "Müşteri", "musteri_payi_%": "Müşteri payı %", "ciro": "Ciro (R$)",
        "ciro_payi_%": "Ciro payı %", "ort_harcama": "Ort. harcama", "ort_siparis_degeri": "Ort. sipariş",
        "ort_recency_gun": "Son alımdan gün", "ort_alisveris_gunu": "Alışveriş günü",
        "ort_yorum_puani": "Yorum puanı"}).round(2), width="stretch")
    st.caption("Puanlar tüm müşteriler üzerinden hesaplandı; filtre yalnızca hangi müşterilerin gösterildiğini "
               "değiştirir. Paylar seçili müşterilere göredir.")

# ------------------------------------------------------------------ churn
with tabs[3]:
    W = st.radio("Churn eşiği (teslimattan sonra gün)", list(config.CHURN_WINDOWS), horizontal=True,
                 format_func=lambda x: f"{x} gün")
    elig, cnt = churn.churn_population(o_f, c_f, W)
    st.subheader(f"{W} günlük pencere: seçili müşteriler")
    c1, c2, c3 = st.columns(3)
    c1.metric("Analiz popülasyonu", tr(cnt["penceresi_kapanmis"], 0))
    c2.metric("Geri dönen", tr(cnt["geri_donen"], 0))
    c3.metric("Tekrar alım", f"%{tr(elig['y'].mean() * 100, 2)}" if len(elig) else "—")
    if len(elig) >= 200:
        drv = churn.driver_table(elig)
        fac = st.selectbox("Etken", drv["faktor"].unique())
        d = drv[drv["faktor"] == fac].set_index("seviye")
        st.bar_chart(d["tekrar_alim_%"])
        st.dataframe(d[["n", "geri_donen", "tekrar_alim_%", "ga_alt_%", "ga_ust_%"]].round(2).rename(columns={
            "n": "Müşteri", "geri_donen": "Geri dönen", "tekrar_alim_%": "Tekrar alım %", "ga_alt_%": "%95 alt",
            "ga_ust_%": "%95 üst"}), width="stretch")
        st.caption("Güven aralıkları geniş grupları dikkatle okuyun. Bunlar ilişkidir, nedensellik değildir.")
    else:
        st.info("Etken tablosu için seçimde en az 200 müşteri gerekli.")
    st.subheader("Eşik karşılaştırması ve model (tüm veri)")
    st.dataframe(load_table("churn_esik_karsilastirma.csv").set_index("esik_gun").T, width="stretch")
    m = K["churn"][f"{W}g"]["model"]
    st.markdown(f"Lojistik model AUC **{tr(m['auc_lojistik'], 3)}** (%95 aralık {tr(m['auc_lojistik_ga'][0], 3)}–"
                f"{tr(m['auc_lojistik_ga'][1], 3)}); başlangıç kuralı (kısa teslimat) AUC "
                f"**{tr(m['auc_baslangic_teslimat_kurali'], 3)}**; rastgele tahmin 0,500. "
                "Model zayıf: bireysel müşteri hedeflemesi için kullanılmamalı.")

# ------------------------------------------------------------------ sepet
with tabs[4]:
    pairs = load_table("sepet_ciftleri.csv")
    st.subheader("Birlikte alınan kategori çiftleri (tüm veri)")
    mn = st.slider("En az birlikte sipariş", int(pairs["birlikte_siparis"].min()),
                   int(pairs["birlikte_siparis"].max()), int(pairs["birlikte_siparis"].min()))
    view = pairs[pairs["birlikte_siparis"] >= mn]
    st.dataframe(view[["kategori_A", "kategori_B", "birlikte_siparis", "destek_%", "guven_A_B_%", "guven_B_A_%",
                       "lift_tum_siparis", "lift_cok_kategorili", "dusuk_orneklem"]].round(3), width="stretch")
    s = K["sepet"]
    st.caption(f"{s['cok_kategorili_siparis_bilinen']} çok kategorili siparişe dayanır; 30'dan az siparişli "
               f"çiftler ({s['dusuk_orneklemli_cift']} çift) 'düşük örneklem' olarak işaretli ve yalnızca yön gösterir.")
    st.subheader("Kategori içi çoklu alım")
    st.dataframe(load_table("sepet_kategori_cok_kalem.csv").round(2), width="stretch")

# ------------------------------------------------------------------ tahmin
with tabs[5]:
    t = K["tahmin"]
    series = load_table("tahmin_haftalik_seri.csv").set_index("hafta_baslangic")
    fc = load_table("tahmin_14_hafta.csv").set_index("hafta_baslangic")
    chart = pd.concat([series[["ciro_ham"]].rename(columns={"ciro_ham": "Gerçekleşen"}),
                       fc[["tahmin_taban", "alt_%10", "ust_%90"]].rename(columns={
                           "tahmin_taban": "Tahmin", "alt_%10": "%10 alt", "ust_%90": "%90 üst"})])
    st.subheader("Haftalık ciro ve 14 haftalık tahmin (tüm veri)")
    st.line_chart(chart)
    tot = t["toplam"]
    st.markdown(f"En düşük hatalı model (**{t['en_iyi_model']}**): 14 hafta toplamı **R${tr(tot['toplam_taban'] / 1e6, 2)} "
                f"milyon** (%80 aralık R${tr(tot['toplam_alt_%10'] / 1e6, 2)}–{tr(tot['toplam_ust_%90'] / 1e6, 2)} milyon). "
                f"Başlangıç tahmini (son 4 hafta ortalaması): **R${tr(t['baslangic_modeli_toplam_taban'] / 1e6, 2)} milyon**.")
    st.dataframe(load_table("tahmin_geriye_donuk_test.csv").round(2), width="stretch")
    st.warning(f"Veri yeterli değil: {t['yeterlilik']['hafta_sayisi']} hafta var, yıllık mevsimsellik için en az "
               f"{t['yeterlilik']['mevsimsellik_icin_gereken_hafta']} hafta gerekir. Black Friday tek gözlem.")

# ------------------------------------------------------------------ tanımlar
with tabs[6]:
    st.markdown(f"""
- **Geçerli sipariş:** durumu iptal/ulaşılamaz/oluşturuldu olmayan, kalemi ve ödemesi bulunan, 31 Ağustos 2018'e kadar
  verilmiş sipariş.
- **Müşteri:** `customer_unique_id`. **Tekrar alım:** ilk alışveriş gününden sonraki bir günde verilen sipariş.
- **Kohort:** ilk sipariş ayı. **Gözlem sonu:** {K['tanimlar']['gozlem_sonu']} (sonrasında veri eksik).
- **RFM:** tarih {K['tanimlar']['rfm_tarihi']}; R ve M beşli dilim, F = 1 / 2+.
- **Churn:** ilk siparişin teslimatından sonraki 180 veya 365 gün içinde yeniden alışveriş yapmamak.
- **Sepet:** destek, güven (A→B), lift; kategori düzeyi.
- **Tahmin:** haftalık ciro, kayan başlangıçlı geriye dönük test, başlangıç = son 4 hafta ortalaması.

Ayrıntılı rapor: `reports/yonetici_ozeti.md`.
""")
