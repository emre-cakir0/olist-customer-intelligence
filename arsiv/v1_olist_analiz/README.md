# Olist Müşteri ve Satış Analitiği

Brezilya e-ticaret işlem verisiyle (Olist) kohort analizi, RFM segmentasyonu, müşteri kaybı (churn),
sepet analizi ve basit bir haftalık satış tahmini. Yönetici özeti ayrı bir belge olarak teslim edildi;
bu klasör kodu, tabloları ve grafikleri içerir.

## Çalıştırma

Gereksinimler: Python 3.10+, pandas, numpy, matplotlib, scikit-learn.
(`statsmodels` ve `mlxtend` gerekmez; sönümlü Holt modeli ve birliktelik ölçüleri elle yazıldı.)

```
python3 kod/01_prepare.py      <ham_csv_klasoru> <cikti_klasoru>
python3 kod/02_cohort_rfm.py   <cikti_klasoru>
python3 kod/03_churn.py        <cikti_klasoru>
python3 kod/04_basket.py       <cikti_klasoru>
python3 kod/05_forecast.py     <cikti_klasoru>
python3 kod/06_verify.py       <ham_csv_klasoru> <cikti_klasoru>
```

Adımlar sırayla çalışmalıdır; her biri öncekinin ara dosyalarını okur. Çıktı klasöründe ara dosyalar
(`*.pkl`) ve `key_numbers.json` oluşur. Analiz penceresi (`END`, `SNAPSHOT`) `01_prepare.py` ve
`02_cohort_rfm.py` başında sabittir.

## Veri

Olist Brazilian E-Commerce Public Dataset (Kaggle: `olistbr/brazilian-ecommerce`).
Kullanılan ham dosyalar: `olist_orders_dataset`, `olist_customers_dataset`, `olist_order_items_dataset`,
`olist_order_payments_dataset`, `olist_order_reviews_dataset`, `olist_products_dataset`,
`product_category_name_translation`. (`geolocation` ve `sellers` kullanılmadı.)

## Temel tanımlar

- **Geçerli sipariş:** durumu iptal / ulaşılamaz / oluşturuldu olmayan, kalemi ve ödemesi olan, 31 Ağustos 2018'e
  kadar verilmiş sipariş. Sonuç: 98.197 sipariş, 94.982 müşteri.
- **Müşteri:** `customer_unique_id` (`customer_id` her siparişte değişir).
- **Ciro:** sipariş başına ödeme tutarları toplamı (kargo dahil), R$.
- **Tekrar alım:** ilk alışveriş gününden sonraki bir günde verilen sipariş. Aynı gün verilen ek siparişler sepet
  bölünmesi sayılır (siparişi birden fazla olan müşteri %3,04, alışveriş günü birden fazla olan %2,17).
- **RFM:** recency = 1 Eylül 2018 ile son alışveriş günü arası gün; frequency = farklı alışveriş günü sayısı;
  monetary = toplam ödeme. Recency ve monetary beşli dilime bölünür; frequency %97,8 oranında 1 olduğundan 1 / 2+ ayrımı
  kullanılır. Segment kuralları `02_cohort_rfm.py` içinde.
- **Churn:** ilk siparişin tesliminden sonra 180 gün içinde yeni bir günde sipariş vermemek. 180 gün, tekrar alanların
  yaklaşık %76'sının döndüğü süredir.
- **Tahmin:** haftalık ciro (2017-01-02 ... 2018-08-13). 20 Ağustos 2018 haftasından itibaren veri eksik olduğundan
  seri orada kesilir. Black Friday haftası olay olarak ayrılır.

## Çıktılar

| Klasör | Dosya | İçerik |
| --- | --- | --- |
| tablolar | `cohort_retention.csv` | Kohort × ay tutunma (%) |
| tablolar | `cohort_repeat_rates.csv` | Kohort başına 90 / 180 günde tekrar alım |
| tablolar | `rfm_segments.csv` | RFM segment özeti |
| tablolar | `musteri_skorlari.csv` | Tek alımlı müşteriler: segment, R, F, M, 180 gün tekrar alım olasılığı |
| tablolar | `churn_drivers.csv` | Etken tablosu (güven aralıklı) |
| tablolar | `churn_model_oranlari.csv` | Lojistik modelin katsayıları |
| tablolar | `sepet_ciftleri.csv` | Kategori çiftleri: destek, güven, lift |
| tablolar | `sepet_buyuklugu_kategori.csv` | Kategori başına çok kalemli sipariş payı |
| tablolar | `tahmin_14_hafta.csv` | 14 haftalık tahmin, %80 aralık, Black Friday senaryosu |
| tablolar | `tahmin_geriye_donuk_test.csv` | Model karşılaştırması (kayan başlangıçlı test) |
| tablolar | `aylik_ciro.csv` | Aylık sipariş ve ciro |
| tablolar | `key_numbers.json` | Özette kullanılan tüm temel rakamlar |
| grafikler | `fig_*.png` | Kohort ısı haritası, RFM, churn etkenleri, model sıralaması, sepet, tahmin |

## Doğrulama

`06_verify.py`, ana hattı kullanmadan doğrudan ham CSV'lerden başlayarak 29 temel rakamı (sipariş ve müşteri sayısı,
ciro, segment büyüklükleri, kohort tutunması, churn popülasyonu, sepet, haftalık seri, geriye dönük test) yeniden
hesaplar ve ana hat çıktısıyla karşılaştırır. Tüm hattın temiz bir klasörde yeniden çalıştırılması aynı sonuçları verdi.

## Sınırlılıklar

- Tekrar alım oranı düşüktür (180 günde %1,8). Veri seti birden çok pazaryerindeki siparişleri kapsıyorsa müşteri kimliği
  pazaryerleri arasında eşleşmeyebilir ve gerçek tekrar alım bundan yüksek olabilir.
- Churn modelinin ayırt etme gücü zayıftır (zaman bazlı testte AUC 0,57); bireysel hedefleme için değil, yön göstermek içindir.
- Sepet analizi yalnızca 726 çok kategorili siparişe dayanır; en az 10 kez birlikte görülen 17 çiftin her birinde örnek 10–70 siparişle sınırlıdır.
- Seri yaklaşık 20 ay (85 hafta) olduğundan yıllık mevsimsellik tahmin edilemedi. Black Friday etkisi tek gözlemdir.
- Maliyet, marj ve edinim maliyeti verisi yoktur; ROI hesabı yapılmadı.
