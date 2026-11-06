# Olist Müşteri ve Satış Analitiği: Yönetici Özeti

> Bu dosya `python run_pipeline.py` ile otomatik üretilir; elle düzenlemeyin. Sayılar `outputs/tables/sonuclar.json` ve her bölümde belirtilen tablolardan gelir.

## İş sorusu

Olist pazaryerinde müşteriler kimdir, ne kadarı geri döner, geri dönmeyi neyle ilişkili görüyoruz, hangi kategoriler birlikte alınır ve önümüzdeki haftaların cirosu ne olabilir? Sonuçta: hangi müşteri segmentine ne yapılmalı?

## Özet

Ciro neredeyse tamamen yeni müşteriden geliyor: Ocak–Temmuz 2018 cirosunun %97,4'ü müşterilerin ilk alışveriş gününden. 94.982 müşterinin %97,8'i yalnızca bir gün alışveriş yapmış.

- **Değer iki segmentte yoğun.** "Yeni - yüksek sepet" ve "Kayıp - yüksek değerli" müşterilerin %30,6'sı, cironun %56,6'sı.
- **Tekrar alım çok düşük.** İlk siparişin tesliminden sonraki 180 günde %1,8, 365 günde %3,1. Tekrar alanların medyanı 74 günde dönüyor.
- **Teslimat süresiyle ilişki eşiğe bağlı.** 180 günlük pencerede 7 günde teslim edilenlerin %2,04'ü, 21 günden uzun sürenlerin %1,38'i geri dönüyor (p = 0,002, çoklu karşılaştırma düzeltmesinden sonra da anlamlı). 365 günlük pencerede fark 0,57 puan ve anlamlı değil (p = 0,263). Bu bir ilişkidir; nedensellik değildir.
- **Churn modeli zayıf.** Zaman sıralı testte AUC 0,58; tek değişkenli teslimat kuralı 0,55, rastgele tahmin 0,50. Bireysel hedefleme için yeterli değil.
- **Sepetler küçük.** Siparişlerin %90,1'i tek kalemli; yalnızca %0,8'inde birden çok kategori var.
- **Tahmin belirsiz.** 2018-08-20 – 2018-11-25 için en iyi model R$3,46 milyon (%80 aralık R$2,71–3,76 milyon), başlangıç tahmini R$4,27 milyon veriyor; geriye dönük test farkı yalnızca 1,1 puan.

## Hangi segmente ne yapılmalı

Öncelik, tekrar alım penceresi hâlâ açık olan 36.992 "Yeni" müşteri. Aşağıdaki eylemler **test edilecek hipotezlerdir**; etkileri ölçülmedi. Maliyet ve marj verisi olmadığından getiri (ROI) hesaplanmadı; her eylem kontrol gruplu küçük bir denemeyle başlamalı.

| Strateji | Segment (kural) | Müşteri | Ciro payı | Denenecek | Ölçüt |
| --- | --- | --- | --- | --- | --- |
| Koru | **Şampiyonlar** (F ≥ 2 ve R puanı ≥ 4) | 1.093 | %2,3 | Yorum/referans isteği, yeni fikirleri önce burada dene; indirim gerekmez | 3. alışverişe geçiş |
| Geri kazan (kontrollü) | **Uyuyan sadıklar** (F ≥ 2 ve R puanı ≤ 3) | 970 | %1,9 | Önceki kategorisine göre tek bir hatırlatma | Kontrole göre geri dönüş |
| Savun | **Yeni - yüksek sepet** (F = 1, R puanı ≥ 4, M puanı ≥ 4) | 14.793 | %28,5 | Teslimatı izle; teslimattan sonra tamamlayıcı kategori önerisi dene | 180 günde tekrar alım |
| Savun (düşük maliyet) | **Yeni - standart** (F = 1, R puanı ≥ 4, M puanı ≤ 3) | 22.199 | %10,3 | Yalnızca otomatik e-posta/bildirim | 180 günde tekrar alım |
| Geri kazan (kontrollü) | **Soğuyanlar** (F = 1, R puanı = 3) | 18.617 | %18,2 | Tek, süreli bir geri kazanım mesajı; küçük hücrede dene | Kontrole göre geri dönüş |
| Geri kazan (kontrollü) | **Kayıp - yüksek değerli** (F = 1, R puanı ≤ 2, M puanı ≥ 4) | 14.265 | %28,1 | Küçük deneme; profilini edinim hedeflemesine örnek al | Kontrole göre ek ciro |
| Bırak | **Kayıp - standart** (F = 1, R puanı ≤ 2, M puanı ≤ 3) | 23.045 | %10,7 | Ücretli kampanyadan çıkar, yalnızca ücretsiz kanalda tut | Tasarruf edilen bütçe |

Ölçek: tekrar alan müşteriler tabanın %2,2'si ve cironun %4,2'si. Tekrar alım oranındaki küçük artışlar ciroyu az değiştirir; cironun ana kaynağı ayda ortalama 6.494 yeni müşteri (Ocak–Temmuz 2018).

## Kohort analizi

Kohort, müşterinin **ilk sipariş ayıdır** (2017-01 – 2018-06, 18 kohort). Tekrar alım = ilk alışveriş gününden sonraki bir günde verilen sipariş; aynı gün verilen ek siparişler sepet bölünmesi sayılır. Ağustos 2018 eksik olduğundan son tam ay 2018-07; gözlenmemiş hücreler boştur.

- Ağırlıklı aylık tutunma: 1. ay %0,48, 3. ay %0,26, 6. ay %0,23, 12. ay %0,19. En yüksek hücre %0,71.
- İlk alımdan sonra 30/90/180/365 günde tekrar alım: %0,66 / %1,31 / %2,00 / %3,36 (yalnızca penceresi 2018-08-21 öncesinde kapanan müşteriler).
- Kohortlar arasında 90 günlük oran %0,9–%1,9 bandında; Kasım 2017 (Black Friday) kohortu %1,34.

Kaynak: `outputs/tables/kohort_tutunma.csv`, `kohort_tekrar_oranlari.csv`, grafik `fig_kohort_tutunma.png`.

## RFM segmentasyonu

RFM tarihi **2018-09-01** (son geçerli siparişten sonraki gün). R = bu tarihle son alışveriş günü arasındaki gün, F = farklı alışveriş günü sayısı, M = toplam ödeme (kargo dahil). R ve M tüm müşterilerde beşe eşit dilime bölünür (R sınırları 96, 180, 271, 386 gün; M sınırları R$55, 88, 133, 209); R puanı 5 = en yakın, M puanı 5 = en yüksek. F'nin %97,8'i 1 olduğundan F yalnızca 1 / 2+ olarak ayrılır.

| Segment | Müşteri | Müşteri payı | Ciro payı | Ort. harcama | Son alımdan gün (ort.) | Ort. yorum |
| --- | --- | --- | --- | --- | --- | --- |
| Şampiyonlar | 1.093 | %1,2 | %2,3 | R$327 | 90 | 4,28 |
| Uyuyan sadıklar | 970 | %1,0 | %1,9 | R$315 | 313 | 4,24 |
| Yeni - yüksek sepet | 14.793 | %15,6 | %28,5 | R$303 | 95 | 4,09 |
| Yeni - standart | 22.199 | %23,4 | %10,3 | R$73 | 93 | 4,22 |
| Soğuyanlar | 18.617 | %19,6 | %18,2 | R$154 | 224 | 3,97 |
| Kayıp - yüksek değerli | 14.265 | %15,0 | %28,1 | R$310 | 398 | 4,07 |
| Kayıp - standart | 23.045 | %24,3 | %10,7 | R$73 | 400 | 4,16 |

En çok harcayan %20 müşteri cironun %53,6'sını oluşturuyor. Tekrar alanların ortalama harcaması R$321, tek alımlıların R$162.

Kaynak: `outputs/tables/rfm_segmentleri.csv`, grafik `fig_rfm_segmentleri.png`.

## Müşteri kaybı (churn): 180 ve 365 gün

Tanım: ilk siparişin **teslimatından** sonraki W gün içinde yeni bir günde sipariş vermeyen müşteri kayıp sayılır. Teslimattan önce yeniden alan 273 müşteri dışarıda kalır; yalnızca W günlük penceresi 2018-08-21 öncesinde kapanan müşteriler sayılır.

| Ölçü | 180 gün | 365 gün |
| --- | --- | --- |
| Son alışverişi eşikten eski müşteri | %59,9 | %22,8 |
| Tekrar alanların bu sürede dönen payı | %75,9 | %95,8 |
| Analiz popülasyonu (penceresi kapanmış) | 50.232 | 18.496 |
| En geç ilk teslimat | 2018-02-22 | 2017-08-21 |
| Tekrar alım / churn | %1,79 / %98,2 | %3,11 / %96,9 |
| Teslimat ≤7 gün vs >21 gün | %2,04 vs %1,38 (p = 0,002) | %3,23 vs %2,66 (p = 0,263) |
| Model AUC / başlangıç kuralı AUC | 0,576 / 0,552 | 0,548 / 0,534 |

Eşik seçimi sonucu değiştiriyor: 365 gün tekrar alanların neredeyse tamamını yakalıyor ama yalnızca 2017-08-21 öncesi teslim edilen, daha küçük ve daha eski bir müşteri grubunu kapsıyor; 180 gün daha güncel ve büyük bir grubu kapsıyor ama tekrar alanların yaklaşık dörtte birini kaçırıyor. Teslimat süresi bulgusu yalnızca 180 günlük pencerede istatistiksel olarak anlamlı. Rapor ana eşik olarak 180 günü kullanıyor; sonuçları 365 günle birlikte okuyun.

İkili karşılaştırmalar (180 gün; 5 test, Bonferroni düzeltmesi):

| Karşılaştırma | A | B | Fark (puan) | p | Düzeltilmiş p |
| --- | --- | --- | --- | --- | --- |
| Teslimat ≤7 gün vs >21 gün | %2,04 (n=11.128) | %1,38 (n=6.143) | 0,66 | 0,002 | 0,010 |
| Zamanında vs >7 gün gecikmiş | %1,81 (n=47.250) | %1,25 (n=1.280) | 0,56 | 0,136 | 0,678 |
| Yorum 5 vs 1 | %1,92 (n=29.539) | %1,49 (n=4.355) | 0,43 | 0,050 | 0,251 |
| 3+ kalem vs 1 kalem | %2,54 (n=1.102) | %1,74 (n=45.288) | 0,80 | 0,045 | 0,225 |
| bed_bath_table vs cool_stuff | %2,43 (n=4.945) | %1,11 (n=2.422) | 1,31 | < 0,001 | < 0,001 |

Model: lojistik regresyon, zaman sıralı doğrulama (teslimatı 2017-10-31 ve öncesi eğitim, sonrası test; test 22.136 müşteri, 342 geri dönüş). AUC 0,576 (%95 aralık 0,546–0,611); başlangıç kuralı "teslimat ne kadar kısaysa o kadar olası" AUC 0,552 (0,516–0,582). Aralıklar örtüşüyor: model basit kuraldan belirgin biçimde iyi değil. En yüksek skorlu %10 dilim geri dönenlerin %14,6'sını yakalıyor (lift 1,46). 365 günde model AUC 0,548, başlangıç 0,534.

Kaynak: `churn_esik_karsilastirma.csv`, `churn_etkenler_180g.csv`, `churn_etkenler_365g.csv`, `churn_testler_180g.csv`, `churn_model_desil_180g.csv`; grafikler `fig_churn_etkenler.png`, `fig_churn_esik_karsilastirma.png`, `fig_churn_model_desil.png`.

## Sepet analizi

Siparişlerin %90,1'i tek kalemli, %9,9'u çok kalemli (bunun 9,1 puanı aynı kategoriden). Çok kalemli siparişler ortalama R$249, tek kalemliler R$151.

Kategori çiftleri kategorisi bilinen 726 çok kategorili siparişe dayanıyor. En az 10 kez birlikte görülen 17 çift var; birlikte sipariş sayıları 10–70 ve 15 çift 30'un altında. Destek = çifti içeren sipariş / tüm siparişler; güven A→B = A'yı içeren siparişlerde B'nin de bulunma payı; lift = destek / (P(A)·P(B)). Tüm siparişlere göre lift neredeyse her çiftte 1'in altında, çünkü siparişlerin %99'u tek kategorili; bu yüzden çok kategorili sepetler içindeki lift de verildi.

| Çift (A + B) | Birlikte sipariş | Destek | Güven A→B (%95 aralık) | Güven B→A (%95 aralık) | Lift (tüm) | Lift (çok kategorili) | Örneklem |
| --- | --- | --- | --- | --- | --- | --- | --- |
| bed_bath_table + furniture_decor | 70 | %0,071 | %0,74 (0,59–0,94) | %1,09 (0,86–1,37) | 0,11 | 1,26 | yeterli |
| bed_bath_table + home_confort | 43 | %0,044 | %0,46 (0,34–0,62) | %10,83 (8,14–14,27) | 1,13 | 3,15 | yeterli |
| furniture_decor + housewares | 24 | %0,024 | %0,37 (0,25–0,56) | %0,41 (0,28–0,61) | 0,06 | 0,84 | düşük |
| baby + cool_stuff | 20 | %0,020 | %0,70 (0,45–1,07) | %0,55 (0,36–0,85) | 0,19 | 2,37 | düşük |
| bed_bath_table + housewares | 20 | %0,020 | %0,21 (0,14–0,33) | %0,34 (0,22–0,53) | 0,04 | 0,72 | düşük |
| baby + toys | 19 | %0,019 | %0,66 (0,42–1,03) | %0,49 (0,32–0,77) | 0,17 | 2,97 | düşük |
| baby + bed_bath_table | 17 | %0,017 | %0,59 (0,37–0,95) | %0,18 (0,11–0,29) | 0,06 | 0,67 | düşük |
| furniture_decor + garden_tools | 17 | %0,017 | %0,26 (0,17–0,42) | %0,49 (0,30–0,78) | 0,07 | 0,83 | düşük |

Düşük sipariş sayısı güven aralıklarını genişletiyor: örneğin home_confort → bed_bath_table kuralının güveni %10,8, ama %95 aralığı %8,1–%14,3. 30'dan az siparişe dayanan çiftler yalnızca yön gösterir.

Kategori içi çoklu alım daha yaygın: ilk kalemin kategorisine göre çok kalemli sipariş payı furniture_decor %20,4, garden_tools %16,2, bed_bath_table %14,5. Tekrar alan 2.063 müşterinin %36,0'ı tek kategoride kalmış, %39,6'sı ilk kategorisine dönmüş.

Kaynak: `sepet_ciftleri.csv`, `sepet_kategori_cok_kalem.csv`, grafik `fig_sepet_ciftleri.png`.

## Haftalık satış tahmini

**Veri yeterli değil:** seri 2017-01-02 – 2018-08-13 arası 85 hafta; yıllık mevsimsellik için en az 104 hafta gerekir. Mevsimsel model kurulmadı. Seri 20 Ağustos 2018 haftasından önce kesildi, çünkü veri 22 Ağustos'tan sonra azalıyor. Black Friday 2017 haftası (R$473 bin, önceki iki haftanın 2,43 katı) tek bir olay olarak ayrıldı.

Doğrulama: zaman sıralı, kayan başlangıçlı geriye dönük test; her başlangıçta model yalnızca o haftaya kadarki veriyi görür ve sonraki 1–14 haftayı tahmin eder. Başlangıç tahmini: son 4 haftanın ortalaması.

| Yöntem | WAPE 1–14 hafta | Yanlılık (+ fazla tahmin) | Başlangıca göre (puan) |
| --- | --- | --- | --- |
| Log-doğrusal trend (son 26 hafta) | %17,9 | +%7,9 | 1,09 |
| Sönümlü Holt (log ölçeği) | %18,8 | −%8,1 | 0,26 |
| Naif: son 4 hafta ortalaması (başlangıç) | %19,0 | −%8,6 | 0,00 |
| Naif: son 13 hafta ortalaması | %21,5 | −%13,7 | −2,48 |

En düşük hata Log-doğrusal trend (son 26 hafta) modelinde (%17,9), başlangıç tahmininden yalnızca 1,1 puan iyi. 2018-08-20 – 2018-11-25 (14 hafta) için bu model R$3,46 milyon veriyor (haftada R$245–250 bin); %80 aralık R$2,71–3,76 milyon (modelin 42 geçmiş 14 haftalık toplamındaki gerçek/tahmin oranlarından, medyan oran 0,97). Başlangıç tahmini aynı dönem için R$4,27 milyon veriyor. İki yöntem geçmişte benzer hata yaptığı hâlde toplamlar arasında R$804 bin fark var; tahmini tek bir sayı olarak değil, bu aralık olarak okuyun.

Bağlam: 2018 Mart–Temmuz aylık ciro R$1,02–1,16 milyon (ortalama R$1,10 milyon). Ocak–Temmuz cirosu 2017'ye göre %161 yüksek; bu fark büyük ölçüde 2017'nin düşük başlangıcından geliyor. Black Friday etkisi 2018'de tekrarlanırsa 14 haftalık toplam R$3,81 milyon olur (tek gözleme dayanan senaryo).

Kaynak: `tahmin_geriye_donuk_test.csv`, `tahmin_14_hafta.csv`, `tahmin_haftalik_seri.csv`, `aylik_ciro.csv`, grafik `fig_tahmin.png`.

## Sınırlılıklar

- Maliyet, marj ve müşteri edinim maliyeti verisi yok; getiri (ROI) hesaplanmadı.
- Tekrar alım çok düşük. Veri seti birden çok pazaryerindeki siparişleri kapsıyorsa müşteri kimliği pazaryerleri arasında eşleşmeyebilir ve gerçek tekrar alım daha yüksek olabilir; bu veriden ayırt edilemez.
- Veri 22 Ağustos 2018'den sonra eksik (son sipariş 2018-08-29); gözlem pencereleri 2018-08-21'de biter.
- Churn bulguları ilişkidir; model zayıf (AUC ≈ 0,58). Teslimat süresi etkisi 365 günlük eşikte doğrulanmadı.
- Sepet analizi 726 çok kategorili siparişe dayanıyor.
- Tahmin 85 haftalık seriye dayanıyor; mevsimsellik yok, Black Friday tek gözlem, model seçimi toplamı belirgin biçimde değiştiriyor.

## Başka bir perakendeciye uyarlamak için gerekenler

Bu sonuçlar Olist'e aittir ve başka bir şirkete genellenmemelidir. Aynı analizi başka bir perakendecide (ör. hızlı tüketim veya market zinciri) kurmak için gerekenler:

- **Ek veri:** ürün maliyeti ve marj, kampanya/indirim kayıtları ve maliyetleri, müşteri edinim kanalı ve maliyeti, iade ve iptaller, mağaza/depo ve teslimat bölgesi, ürün (SKU) düzeyinde katalog, sadakat kartı veya giriş yapmış kullanıcı kimliği.
- **Uyarlamalar:** churn eşiği alışveriş sıklığına göre yeniden seçilmeli (sık alışverişte gün/hafta ölçeği); RFM'de F beşli dilime bölünebilir; sepet analizi kategori yerine ürün düzeyinde yapılabilir; tahmin en az iki yıllık veriyle haftalık mevsimsellik ve tatil/kampanya takvimiyle kurulmalı; öneriler kontrol gruplu deneylerle ölçülmeli.

