"""Yönetici özetini (Markdown) sonuclar.json içeriğinden üretir.

Rapordaki her sayı bu dosyada `K` sözlüğünden okunur; hat yeniden çalıştırıldığında rapor da yeniden yazılır.
Her bölümün sonunda sayıların geldiği tablo dosyası belirtilir.
"""
from __future__ import annotations

from pathlib import Path


def n(x, nd=1):
    """Türkçe sayı biçimi."""
    s = f"{x:,.{nd}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".").replace("-", "−")


def p(x, nd=1):
    return f"%{n(x, nd)}"


def money(x):
    if abs(x) >= 1e6:
        return f"R${n(x / 1e6, 2)} milyon"
    if abs(x) >= 1e4:
        return f"R${n(x / 1e3, 0)} bin"
    return f"R${n(x, 0)}"


# ------------------------------------------------------------------ Türkçe ekler
# Sayıdan sonra gelen iyelik eki, sayının okunuşundaki son kelimeye göre seçilir (ör. %30,6'sı, %97,4'ü).
_DIGIT = {"1": "i", "2": "si", "3": "ü", "4": "ü", "5": "i", "6": "sı", "7": "si", "8": "i", "9": "u"}
_TENS = {"1": "u", "2": "si", "3": "u", "4": "ı", "5": "si", "6": "ı", "7": "i", "8": "i", "9": "ı"}
_NDE = {"sı": "sında", "si": "sinde", "i": "inde", "ı": "ında", "u": "unda", "ü": "ünde"}
_NI = {"sı": "sını", "si": "sini", "i": "ini", "ı": "ını", "u": "unu", "ü": "ünü"}


def _iyelik(text: str) -> str:
    digits = text.replace("%", "").replace(".", "")
    part = digits.split(",")[-1] if "," in digits else digits
    part = part.rstrip()
    if not part or set(part) == {"0"}:
        if "," in digits:  # ör. 2,0 -> "iki virgül sıfır"
            return "ı"
        return "ı"
    if part[-1] != "0":
        return _DIGIT[part[-1]]
    if len(part) >= 2 and part[-2] != "0":
        return _TENS[part[-2]]
    if len(part) >= 3 and part[-3] != "0" and part[-2:] == "00":
        return "ü"   # yüz
    return "i"       # bin


def ps(x, nd=1):
    """Yüzde + iyelik eki: %30,6'sı."""
    t = p(x, nd)
    return f"{t}'{_iyelik(t)}"


def psn(x, nd=1):
    """Yüzde + iyelik + belirtme: %53,6'sını."""
    t = p(x, nd)
    return f"{t}'{_NI[_iyelik(t)]}"


def psl(x, nd=1):
    """Yüzde + iyelik + bulunma: %0,8'inde."""
    t = p(x, nd)
    return f"{t}'{_NDE[_iyelik(t)]}"


def money_range(a, b):
    if a >= 1e6 and b >= 1e6:
        return f"R${n(a / 1e6, 2)}–{n(b / 1e6, 2)} milyon"
    if 1e4 <= a < 1e6 and 1e4 <= b < 1e6:
        return f"R${n(a / 1e3, 0)}–{n(b / 1e3, 0)} bin"
    return f"{money(a)}–{money(b)}"


def pval(x):
    return "< 0,001" if x < 0.001 else n(x, 3)


def table(header, rows):
    out = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" for _ in header) + " |"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def _seg(K, name):
    return next(s for s in K["rfm"]["segmentler"] if s["segment"] == name)


def _test(K, w, name):
    return next(t for t in K["churn"][f"{w}g"]["testler"] if t["karsilastirma"] == name)


def _cmp(K, w):
    return next(r for r in K["churn"]["esik_karsilastirma"] if r["esik_gun"] == w)


def build(K) -> str:
    v, c, r, s, t = K["veri"], K["kohort"], K["rfm"], K["sepet"], K["tahmin"]
    tn = K["tanimlar"]
    c180, c365 = _cmp(K, 180), _cmp(K, 365)
    m180, m365 = K["churn"]["180g"]["model"], K["churn"]["365g"]["model"]
    d180, d365 = _test(K, 180, "Teslimat ≤7 gün vs >21 gün"), _test(K, 365, "Teslimat ≤7 gün vs >21 gün")
    hi = [_seg(K, "Yeni - yüksek sepet"), _seg(K, "Kayıp - yüksek değerli")]
    new_n = _seg(K, "Yeni - yüksek sepet")["musteri"] + _seg(K, "Yeni - standart")["musteri"]
    y = r["yogunlasma"]
    tot = t["toplam"]
    met = {m["model"]: m for m in t["metrikler"]}
    best, base = met[t["en_iyi_model"]], met[t["baslangic_modeli"]]
    gap = c["ikinci_alima_sure"]
    deliv_sig_180 = d180["p_bonferroni"] < 0.05
    deliv_sig_365 = d365["p_bonferroni"] < 0.05

    L = []
    A = L.append
    A("# Olist Müşteri ve Satış Analitiği: Yönetici Özeti")
    A("")
    A("> Bu dosya `python run_pipeline.py` ile otomatik üretilir; elle düzenlemeyin. "
      "Sayılar `outputs/tables/sonuclar.json` ve her bölümde belirtilen tablolardan gelir.")
    A("")
    A("## İş sorusu")
    A("")
    A("Olist pazaryerinde müşteriler kimdir, ne kadarı geri döner, geri dönmeyi neyle ilişkili görüyoruz, "
      "hangi kategoriler birlikte alınır ve önümüzdeki haftaların cirosu ne olabilir? Sonuçta: hangi müşteri "
      "segmentine ne yapılmalı?")
    A("")
    A("## Özet")
    A("")
    A(f"Ciro neredeyse tamamen yeni müşteriden geliyor: Ocak–Temmuz 2018 cirosunun "
      f"{ps(v['ocak_temmuz_2018_ilk_gun_ciro_payi_%'])} müşterilerin ilk alışveriş gününden. "
      f"{n(v['musteri'], 0)} müşterinin {ps(v['tek_alisveris_gunu_%'])} yalnızca bir gün alışveriş yapmış.")
    A("")
    A(f"- **Değer iki segmentte yoğun.** \"Yeni - yüksek sepet\" ve \"Kayıp - yüksek değerli\" müşterilerin "
      f"{ps(hi[0]['musteri_payi_%'] + hi[1]['musteri_payi_%'])}, cironun "
      f"{ps(hi[0]['ciro_payi_%'] + hi[1]['ciro_payi_%'])}.")
    A(f"- **Tekrar alım çok düşük.** İlk siparişin tesliminden sonraki 180 günde {p(c180['tekrar_alim_%'])}, "
      f"365 günde {p(c365['tekrar_alim_%'])}. Tekrar alanların medyanı {n(gap['medyan_gun'], 0)} günde dönüyor.")
    A(f"- **Teslimat süresiyle ilişki eşiğe bağlı.** 180 günlük pencerede 7 günde teslim edilenlerin "
      f"{ps(d180['oran_A_%'], 2)}, 21 günden uzun sürenlerin {ps(d180['oran_B_%'], 2)} geri dönüyor "
      f"(p = {pval(d180['p_degeri'])}"
      + (", çoklu karşılaştırma düzeltmesinden sonra da anlamlı)" if deliv_sig_180 else ")")
      + f". 365 günlük pencerede fark {n(d365['fark_puan'], 2)} puan ve "
      + ("anlamlı." if deliv_sig_365 else f"anlamlı değil (p = {pval(d365['p_degeri'])}).")
      + " Bu bir ilişkidir; nedensellik değildir.")
    A(f"- **Churn modeli zayıf.** Zaman sıralı testte AUC {n(m180['auc_lojistik'], 2)}; tek değişkenli teslimat "
      f"kuralı {n(m180['auc_baslangic_teslimat_kurali'], 2)}, rastgele tahmin 0,50. Bireysel hedefleme için "
      f"yeterli değil.")
    A(f"- **Sepetler küçük.** Siparişlerin {ps(s['yapi']['tek_kalemli_%'])} tek kalemli; yalnızca "
      f"{psl(s['yapi']['cok_kategorili_%'])} birden çok kategori var.")
    A(f"- **Tahmin belirsiz.** {t['tahmin_baslangic']} – {t['tahmin_bitis']} için en iyi model "
      f"{money(tot['toplam_taban'])} (%80 aralık {money_range(tot['toplam_alt_%10'], tot['toplam_ust_%90'])}), "
      f"başlangıç tahmini {money(t['baslangic_modeli_toplam_taban'])} veriyor; geriye dönük test farkı yalnızca "
      f"{n(best['baslangica_gore_iyilesme_puan'], 1)} puan.")
    A("")
    A("## Hangi segmente ne yapılmalı")
    A("")
    A(f"Öncelik, tekrar alım penceresi hâlâ açık olan {n(new_n, 0)} \"Yeni\" müşteri. Aşağıdaki eylemler "
      "**test edilecek hipotezlerdir**; etkileri ölçülmedi. Maliyet ve marj verisi olmadığından getiri (ROI) "
      "hesaplanmadı; her eylem kontrol gruplu küçük bir denemeyle başlamalı.")
    A("")
    rows = []
    plan = {
        "Şampiyonlar": ("Koru", "Yorum/referans isteği, yeni fikirleri önce burada dene; indirim gerekmez",
                        "3. alışverişe geçiş"),
        "Uyuyan sadıklar": ("Geri kazan (kontrollü)", "Önceki kategorisine göre tek bir hatırlatma",
                            "Kontrole göre geri dönüş"),
        "Yeni - yüksek sepet": ("Savun", "Teslimatı izle; teslimattan sonra tamamlayıcı kategori önerisi dene",
                                "180 günde tekrar alım"),
        "Yeni - standart": ("Savun (düşük maliyet)", "Yalnızca otomatik e-posta/bildirim",
                            "180 günde tekrar alım"),
        "Soğuyanlar": ("Geri kazan (kontrollü)", "Tek, süreli bir geri kazanım mesajı; küçük hücrede dene",
                       "Kontrole göre geri dönüş"),
        "Kayıp - yüksek değerli": ("Geri kazan (kontrollü)", "Küçük deneme; profilini edinim hedeflemesine örnek al",
                                   "Kontrole göre ek ciro"),
        "Kayıp - standart": ("Bırak", "Ücretli kampanyadan çıkar, yalnızca ücretsiz kanalda tut",
                             "Tasarruf edilen bütçe"),
    }
    for sg in r["segmentler"]:
        a, b, m = plan[sg["segment"]]
        rows.append([a, f"**{sg['segment']}** ({sg['kural']})", n(sg["musteri"], 0), p(sg["ciro_payi_%"]), b, m])
    A(table(["Strateji", "Segment (kural)", "Müşteri", "Ciro payı", "Denenecek", "Ölçüt"], rows))
    A("")
    A(f"Ölçek: tekrar alan müşteriler tabanın {ps(y['tekrar_alan_musteri_payi_%'])} ve cironun "
      f"{ps(y['tekrar_alan_ciro_payi_%'])}. Tekrar alım oranındaki küçük artışlar ciroyu az değiştirir; "
      f"cironun ana kaynağı ayda ortalama {n(v['ocak_temmuz_2018_aylik_yeni_musteri_ort'], 0)} yeni müşteri "
      f"(Ocak–Temmuz 2018).")
    A("")
    A("## Kohort analizi")
    A("")
    A(f"Kohort, müşterinin **ilk sipariş ayıdır** ({c['ilk_kohort']} – {c['son_kohort']}, {c['kohort_sayisi']} "
      f"kohort). Tekrar alım = ilk alışveriş gününden sonraki bir günde verilen sipariş; aynı gün verilen ek "
      f"siparişler sepet bölünmesi sayılır. Ağustos 2018 eksik olduğundan son tam ay {tn['son_tam_ay']}; "
      f"gözlenmemiş hücreler boştur.")
    A("")
    w = c["agirlikli_tutunma_%"]
    A(f"- Ağırlıklı aylık tutunma: 1. ay {p(w['1'], 2)}, 3. ay {p(w['3'], 2)}, 6. ay {p(w['6'], 2)}, "
      f"12. ay {p(w['12'], 2)}. En yüksek hücre {p(c['en_yuksek_hucre_%'], 2)}.")
    nd = c["n_gunde_tekrar_%"]
    A(f"- İlk alımdan sonra 30/90/180/365 günde tekrar alım: {p(nd['30'], 2)} / {p(nd['90'], 2)} / "
      f"{p(nd['180'], 2)} / {p(nd['365'], 2)} (yalnızca penceresi {tn['gozlem_sonu']} öncesinde kapanan müşteriler).")
    A(f"- Kohortlar arasında 90 günlük oran {p(c['kohort_90g_min_%'], 1)}–{p(c['kohort_90g_max_%'], 1)} bandında; "
      f"Kasım 2017 (Black Friday) kohortu {p(c['kasim_2017_90g_%'], 2)}.")
    A("")
    A("Kaynak: `outputs/tables/kohort_tutunma.csv`, `kohort_tekrar_oranlari.csv`, grafik `fig_kohort_tutunma.png`.")
    A("")
    A("## RFM segmentasyonu")
    A("")
    cuts = r["kesim_noktalari"]
    A(f"RFM tarihi **{tn['rfm_tarihi']}** (son geçerli siparişten sonraki gün). R = bu tarihle son alışveriş günü "
      f"arasındaki gün, F = farklı alışveriş günü sayısı, M = toplam ödeme (kargo dahil). R ve M tüm müşterilerde "
      f"beşe eşit dilime bölünür (R sınırları {', '.join(n(x, 0) for x in cuts['R_sinirlari_gun'])} gün; M sınırları "
      f"R${', '.join(n(x, 0) for x in cuts['M_sinirlari_R$'])}); R puanı 5 = en yakın, M puanı 5 = en yüksek. "
      f"F'nin {ps(v['tek_alisveris_gunu_%'])} 1 olduğundan F yalnızca 1 / 2+ olarak ayrılır.")
    A("")
    A(table(["Segment", "Müşteri", "Müşteri payı", "Ciro payı", "Ort. harcama", "Son alımdan gün (ort.)",
             "Ort. yorum"],
            [[sg["segment"], n(sg["musteri"], 0), p(sg["musteri_payi_%"]), p(sg["ciro_payi_%"]),
              f"R${n(sg['ort_harcama'], 0)}", n(sg["ort_recency_gun"], 0), n(sg["ort_yorum_puani"], 2)]
             for sg in r["segmentler"]]))
    A("")
    A(f"En çok harcayan %20 müşteri cironun {psn(y['ilk_%20_ciro_payi'])} oluşturuyor. Tekrar alanların "
      f"ortalama harcaması {money(y['tekrar_alan_ort_harcama'])}, tek alımlıların {money(y['tek_alimli_ort_harcama'])}.")
    A("")
    A("Kaynak: `outputs/tables/rfm_segmentleri.csv`, grafik `fig_rfm_segmentleri.png`.")
    A("")
    A("## Müşteri kaybı (churn): 180 ve 365 gün")
    A("")
    A(f"Tanım: ilk siparişin **teslimatından** sonraki W gün içinde yeni bir günde sipariş vermeyen müşteri kayıp "
      f"sayılır. Teslimattan önce yeniden alan {n(K['churn']['180g']['populasyon']['teslimattan_once_tekrar_alan_cikarilan'], 0)} "
      f"müşteri dışarıda kalır; yalnızca W günlük penceresi {tn['gozlem_sonu']} öncesinde kapanan müşteriler sayılır.")
    A("")
    A(table(["Ölçü", "180 gün", "365 gün"], [
        ["Son alışverişi eşikten eski müşteri", p(c180["son_alimi_esikten_eski_musteri_%"]),
         p(c365["son_alimi_esikten_eski_musteri_%"])],
        ["Tekrar alanların bu sürede dönen payı", p(c180["tekrar_alanlarin_esik_icinde_donen_payi_%"]),
         p(c365["tekrar_alanlarin_esik_icinde_donen_payi_%"])],
        ["Analiz popülasyonu (penceresi kapanmış)", n(c180["penceresi_kapanmis_musteri"], 0),
         n(c365["penceresi_kapanmis_musteri"], 0)],
        ["En geç ilk teslimat", c180["en_gec_ilk_teslimat"], c365["en_gec_ilk_teslimat"]],
        ["Tekrar alım / churn", f"{p(c180['tekrar_alim_%'], 2)} / {p(c180['churn_%'], 1)}",
         f"{p(c365['tekrar_alim_%'], 2)} / {p(c365['churn_%'], 1)}"],
        ["Teslimat ≤7 gün vs >21 gün", f"{p(c180['teslimat_7g_alti_tekrar_%'], 2)} vs "
         f"{p(c180['teslimat_21g_ustu_tekrar_%'], 2)} (p = {pval(c180['teslimat_farki_p'])})",
         f"{p(c365['teslimat_7g_alti_tekrar_%'], 2)} vs {p(c365['teslimat_21g_ustu_tekrar_%'], 2)} "
         f"(p = {pval(c365['teslimat_farki_p'])})"],
        ["Model AUC / başlangıç kuralı AUC", f"{n(c180['model_auc'], 3)} / {n(c180['baslangic_auc'], 3)}",
         f"{n(c365['model_auc'], 3)} / {n(c365['baslangic_auc'], 3)}"],
    ]))
    A("")
    A("Eşik seçimi sonucu değiştiriyor: 365 gün tekrar alanların neredeyse tamamını yakalıyor ama yalnızca "
      f"{c365['en_gec_ilk_teslimat']} öncesi teslim edilen, daha küçük ve daha eski bir müşteri grubunu "
      "kapsıyor; 180 gün daha güncel ve büyük bir grubu kapsıyor ama tekrar alanların yaklaşık dörtte birini "
      "kaçırıyor. Teslimat süresi bulgusu yalnızca 180 günlük pencerede istatistiksel olarak anlamlı. Rapor ana "
      "eşik olarak 180 günü kullanıyor; sonuçları 365 günle birlikte okuyun.")
    A("")
    A("İkili karşılaştırmalar (180 gün; 5 test, Bonferroni düzeltmesi):")
    A("")
    A(table(["Karşılaştırma", "A", "B", "Fark (puan)", "p", "Düzeltilmiş p"],
            [[tt["karsilastirma"], f"{p(tt['oran_A_%'], 2)} (n={n(tt['n_A'], 0)})",
              f"{p(tt['oran_B_%'], 2)} (n={n(tt['n_B'], 0)})", n(tt["fark_puan"], 2), pval(tt["p_degeri"]),
              pval(tt["p_bonferroni"])] for tt in K["churn"]["180g"]["testler"]]))
    A("")
    A(f"Model: lojistik regresyon, zaman sıralı doğrulama (teslimatı {m180['egitim_bitis']} ve öncesi eğitim, "
      f"sonrası test; test {n(m180['test_n'], 0)} müşteri, {m180['test_pozitif']} geri dönüş). AUC "
      f"{n(m180['auc_lojistik'], 3)} (%95 aralık {n(m180['auc_lojistik_ga'][0], 3)}–{n(m180['auc_lojistik_ga'][1], 3)}); "
      f"başlangıç kuralı \"teslimat ne kadar kısaysa o kadar olası\" AUC {n(m180['auc_baslangic_teslimat_kurali'], 3)} "
      f"({n(m180['auc_baslangic_ga'][0], 3)}–{n(m180['auc_baslangic_ga'][1], 3)}). Aralıklar örtüşüyor: model "
      f"basit kuraldan belirgin biçimde iyi değil. En yüksek skorlu %10 dilim geri dönenlerin "
      f"{psn(m180['ilk_desil_yakalama_%'])} yakalıyor (lift {n(m180['ilk_desil_lift'], 2)}). 365 günde model AUC "
      f"{n(m365['auc_lojistik'], 3)}, başlangıç {n(m365['auc_baslangic_teslimat_kurali'], 3)}.")
    A("")
    A("Kaynak: `churn_esik_karsilastirma.csv`, `churn_etkenler_180g.csv`, `churn_etkenler_365g.csv`, "
      "`churn_testler_180g.csv`, `churn_model_desil_180g.csv`; grafikler `fig_churn_etkenler.png`, "
      "`fig_churn_esik_karsilastirma.png`, `fig_churn_model_desil.png`.")
    A("")
    A("## Sepet analizi")
    A("")
    st = s["yapi"]
    A(f"Siparişlerin {ps(st['tek_kalemli_%'])} tek kalemli, {ps(st['cok_kalemli_%'])} çok kalemli (bunun "
      f"{n(st['cok_kalemli_tek_kategori_%'], 1)} puanı aynı kategoriden). Çok kalemli siparişler ortalama "
      f"{money(st['ort_tutar_cok_kalem'])}, tek kalemliler {money(st['ort_tutar_tek_kalem'])}.")
    A("")
    A(f"Kategori çiftleri kategorisi bilinen {n(s['cok_kategorili_siparis_bilinen'], 0)} çok kategorili siparişe "
      f"dayanıyor. En az 10 kez birlikte görülen {s['cift_sayisi']} çift var; birlikte sipariş sayıları "
      f"{s['cift_min_siparis']}–{s['cift_max_siparis']} ve {s['dusuk_orneklemli_cift']} çift 30'un altında. "
      "Destek = çifti içeren sipariş / tüm siparişler; güven A→B = A'yı içeren siparişlerde B'nin de bulunma payı; "
      "lift = destek / (P(A)·P(B)). Tüm siparişlere göre lift neredeyse her çiftte 1'in altında, çünkü siparişlerin "
      "%99'u tek kategorili; bu yüzden çok kategorili sepetler içindeki lift de verildi.")
    A("")
    rows = []
    for pr in s["ciftler"][:8]:
        rows.append([f"{pr['kategori_A']} + {pr['kategori_B']}", pr["birlikte_siparis"], p(pr["destek_%"], 3),
                     f"{p(pr['guven_A_B_%'], 2)} ({n(pr['guven_A_B_ga_alt_%'], 2)}–{n(pr['guven_A_B_ga_ust_%'], 2)})",
                     f"{p(pr['guven_B_A_%'], 2)} ({n(pr['guven_B_A_ga_alt_%'], 2)}–{n(pr['guven_B_A_ga_ust_%'], 2)})",
                     n(pr["lift_tum_siparis"], 2), n(pr["lift_cok_kategorili"], 2),
                     "düşük" if pr["dusuk_orneklem"] else "yeterli"])
    A(table(["Çift (A + B)", "Birlikte sipariş", "Destek", "Güven A→B (%95 aralık)", "Güven B→A (%95 aralık)",
             "Lift (tüm)", "Lift (çok kategorili)", "Örneklem"], rows))
    A("")
    strong = max(s["ciftler"], key=lambda q: q["guven_B_A_%"] if not q["dusuk_orneklem"] else -1)
    A(f"Düşük sipariş sayısı güven aralıklarını genişletiyor: örneğin {strong['kategori_B']} → "
      f"{strong['kategori_A']} kuralının güveni {p(strong['guven_B_A_%'], 1)}, ama %95 aralığı "
      f"{p(strong['guven_B_A_ga_alt_%'], 1)}–{p(strong['guven_B_A_ga_ust_%'], 1)}. 30'dan az siparişe dayanan "
      "çiftler yalnızca yön gösterir.")
    tk = s["tekrar_alanlar"]
    top3 = s["kategori_cok_kalem"][:3]
    A("")
    A("Kategori içi çoklu alım daha yaygın: ilk kalemin kategorisine göre çok kalemli sipariş payı "
      + ", ".join(f"{q['kategori']} {p(q['cok_kalemli_pay_%'])}" for q in top3)
      + f". Tekrar alan {n(tk['tekrar_alan'], 0)} müşterinin {ps(tk['tek_kategoride_kalan_%'])} tek kategoride "
      f"kalmış, {ps(tk['ilk_kategoriye_donen_%'])} ilk kategorisine dönmüş.")
    A("")
    A("Kaynak: `sepet_ciftleri.csv`, `sepet_kategori_cok_kalem.csv`, grafik `fig_sepet_ciftleri.png`.")
    A("")
    A("## Haftalık satış tahmini")
    A("")
    ye = t["yeterlilik"]
    A(f"**Veri yeterli değil:** seri {ye['seri_baslangic']} – {ye['seri_bitis']} arası {ye['hafta_sayisi']} hafta; "
      f"yıllık mevsimsellik için en az {ye['mevsimsellik_icin_gereken_hafta']} hafta gerekir. Mevsimsel model "
      f"kurulmadı. Seri 20 Ağustos 2018 haftasından önce kesildi, çünkü veri 22 Ağustos'tan sonra azalıyor. Black "
      f"Friday 2017 haftası ({money(t['black_friday_2017_hafta_ciro'])}, önceki iki haftanın "
      f"{n(t['black_friday_carpani'], 2)} katı) tek bir olay olarak ayrıldı.")
    A("")
    A("Doğrulama: zaman sıralı, kayan başlangıçlı geriye dönük test; her başlangıçta model yalnızca o haftaya kadarki "
      "veriyi görür ve sonraki 1–14 haftayı tahmin eder. Başlangıç tahmini: son 4 haftanın ortalaması.")
    A("")
    A(table(["Yöntem", "WAPE 1–14 hafta", "Yanlılık (+ fazla tahmin)", "Başlangıca göre (puan)"],
            [[m["model"] + (" (başlangıç)" if m["baslangic_modeli"] else ""), p(m["WAPE_h1-14_%"]),
              f"{'+' if m['yanlilik_h1-14_%'] > 0 else '−'}{p(abs(m['yanlilik_h1-14_%']))}",
              n(m["baslangica_gore_iyilesme_puan"], 2)] for m in t["metrikler"]]))
    A("")
    q = tot["toplam_oran_q10_q50_q90"]
    A(f"En düşük hata {t['en_iyi_model']} modelinde ({p(best['WAPE_h1-14_%'])}), başlangıç tahmininden yalnızca "
      f"{n(best['baslangica_gore_iyilesme_puan'], 1)} puan iyi. {t['tahmin_baslangic']} – {t['tahmin_bitis']} "
      f"(14 hafta) için bu model {money(tot['toplam_taban'])} veriyor "
      f"(haftada {money_range(t['haftalik_tahmin_min'], t['haftalik_tahmin_max'])}); %80 aralık {money_range(tot['toplam_alt_%10'], tot['toplam_ust_%90'])} "
      f"(modelin {tot['toplam_icin_baslangic_sayisi']} geçmiş 14 haftalık toplamındaki gerçek/tahmin oranlarından, "
      f"medyan oran {n(q[1], 2)}). Başlangıç tahmini aynı dönem için {money(t['baslangic_modeli_toplam_taban'])} "
      f"veriyor. İki yöntem geçmişte benzer hata yaptığı hâlde toplamlar arasında "
      f"{money(t['baslangic_modeli_toplam_taban'] - tot['toplam_taban'])} fark var; tahmini tek bir sayı olarak değil, "
      "bu aralık olarak okuyun.")
    A("")
    A(f"Bağlam: 2018 Mart–Temmuz aylık ciro "
      f"{money_range(t['aylik_2018_mart_temmuz_min'], t['aylik_2018_mart_temmuz_max'])} (ortalama {money(t['aylik_2018_mart_temmuz_ort'])}). Ocak–Temmuz "
      f"cirosu 2017'ye göre {p(t['ocak_temmuz_degisim_%'], 0)} yüksek; bu fark büyük ölçüde 2017'nin düşük "
      f"başlangıcından geliyor. Black Friday etkisi 2018'de tekrarlanırsa 14 haftalık toplam "
      f"{money(tot['toplam_olay_senaryosu'])} olur (tek gözleme dayanan senaryo).")
    A("")
    A("Kaynak: `tahmin_geriye_donuk_test.csv`, `tahmin_14_hafta.csv`, `tahmin_haftalik_seri.csv`, `aylik_ciro.csv`, "
      "grafik `fig_tahmin.png`.")
    A("")
    A("## Sınırlılıklar")
    A("")
    A("- Maliyet, marj ve müşteri edinim maliyeti verisi yok; getiri (ROI) hesaplanmadı.")
    A("- Tekrar alım çok düşük. Veri seti birden çok pazaryerindeki siparişleri kapsıyorsa müşteri kimliği "
      "pazaryerleri arasında eşleşmeyebilir ve gerçek tekrar alım daha yüksek olabilir; bu veriden ayırt edilemez.")
    A(f"- Veri 22 Ağustos 2018'den sonra eksik (son sipariş {v['son_siparis'][:10]}); gözlem pencereleri "
      f"{tn['gozlem_sonu']}'de biter.")
    A(f"- Churn bulguları ilişkidir; model zayıf (AUC ≈ {n(m180['auc_lojistik'], 2)}). Teslimat süresi etkisi "
      f"365 günlük eşikte doğrulanmadı.")
    A(f"- Sepet analizi {n(s['cok_kategorili_siparis_bilinen'], 0)} çok kategorili siparişe dayanıyor.")
    A(f"- Tahmin {ye['hafta_sayisi']} haftalık seriye dayanıyor; mevsimsellik yok, Black Friday tek gözlem, "
      "model seçimi toplamı belirgin biçimde değiştiriyor.")
    A("")
    A("## Başka bir perakendeciye uyarlamak için gerekenler")
    A("")
    A("Bu sonuçlar Olist'e aittir ve başka bir şirkete genellenmemelidir. Aynı analizi başka bir perakendecide "
      "(ör. hızlı tüketim veya market zinciri) kurmak için gerekenler:")
    A("")
    A("- **Ek veri:** ürün maliyeti ve marj, kampanya/indirim kayıtları ve maliyetleri, müşteri edinim kanalı ve "
      "maliyeti, iade ve iptaller, mağaza/depo ve teslimat bölgesi, ürün (SKU) düzeyinde katalog, sadakat kartı "
      "veya giriş yapmış kullanıcı kimliği.")
    A("- **Uyarlamalar:** churn eşiği alışveriş sıklığına göre yeniden seçilmeli (sık alışverişte gün/hafta "
      "ölçeği); RFM'de F beşli dilime bölünebilir; sepet analizi kategori yerine ürün düzeyinde yapılabilir; tahmin "
      "en az iki yıllık veriyle haftalık mevsimsellik ve tatil/kampanya takvimiyle kurulmalı; öneriler kontrol "
      "gruplu deneylerle ölçülmeli.")
    A("")
    return "\n".join(L) + "\n"


def write_report(K, path: Path) -> Path:
    path = Path(path)
    path.write_text(build(K), encoding="utf-8")
    return path
