```
OLIST MÜŞTERİ ROTASI — etkileşimli analiz uygulaması

Nasıl açılır?
  index.html dosyasına çift tıklayın (ya da canlı sürümü açın: https://emre-cakir0.github.io/olist-customer-intelligence/). Tarayıcıda açılır; kurulum, Python ya da internet gerekmez.
  (İnternet varsa özel yazı tipleri yüklenir; yoksa sistem yazı tipiyle aynı şekilde çalışır.)

Neler var?
  Başlangıç       : kaç müşterinin geri geldiği, ana rakamlar
  Kohortlar       : her ayın yeni müşterilerinin sonraki aylarda geri gelme oranı (ısı haritası)
  Geri dönüş      : ikinci alışverişe kadar geçen süre, kaydırıcıyla
  RFM segmentleri : puan sınırları, tıklanabilir segment ızgarası, her segmentin açıklaması ve önerisi
  Müşteri kaybı   : 180 / 365 gün, etkenler, anlamlılık testleri, model ve basit kural karşılaştırması
  Sepet           : sipariş yapısı, birlikte alınan kategoriler (Türkçe), çok ürünlü sipariş payı
  Satış tahmini   : 14 haftalık tahmin, geçmiş testteki hata, Black Friday seçeneği
  Yöntem ve sözlük: veri temizliği, sınırlılıklar, terimlerin açıklaması

Üstteki filtreler (ilk alışveriş ayı, eyalet, RFM segmenti, ilk siparişin kategorisi)
Başlangıç, Kohortlar, Geri dönüş ve RFM bölümlerini anında değiştirir.

Dosyalar
  index.html       sayfa
  stil.css         tasarım
  uygulama.js      hesaplamalar ve grafikler
  veri.js          proje çıktılarından üretilmiş veri (94.982 müşteri)
  veri_hazirla.py  veri.js'i yeniden üretir

Veriyi yenilemek (projede run_pipeline.py yeniden çalıştırıldıysa):
  proje klasöründe:  python docs\veri_hazirla.py .
```
