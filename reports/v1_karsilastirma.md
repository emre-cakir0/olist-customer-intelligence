# İlk sürümle (v1) karşılaştırma

İlk analiz (6 betik, `arsiv/v1_olist_analiz/`) bu projede modüllere taşındı ve her sayı yeniden hesaplandı.
Eski sürümün sayıları doğru kabul edilmedi: aşağıdaki tablo eski `key_numbers.json` ile yeni
`outputs/tables/sonuclar.json` karşılaştırmasıdır.

## Neden bazı sayılar değişti?

1. **Gözlem sonu düzeltmesi.** Veri 22 Ağustos 2018'den sonra keskin biçimde azalıyor (günde ~250 siparişten
   29 Ağustos'ta 11'e). v1 bu kesintiyi yalnızca tahminde dikkate almıştı. Yeni sürümde geri dönüş penceresi
   (kohort hücreleri, N gün içinde tekrar alım, churn penceresi) 21 Ağustos 2018'de biter; Ağustos 2018 de kohort
   tablosunda gözlenmiş ay sayılmaz. Bu yüzden 2018-07 kohortu tablodan çıktı (19 → 18 kohort) ve churn
   popülasyonu küçüldü (52.465 → 50.232).
2. **Churn modeli sadeleşti.** Gradient boosting kaldırıldı (lojistikten iyi değildi); yerine eğitim gerektirmeyen
   tek değişkenli başlangıç kuralı (kısa teslimat = olası geri dönüş) eklendi. Müşteri bazlı olasılık skoru
   dosyası (`musteri_skorlari.csv`) üretilmiyor: model bireysel hedefleme için yeterince güçlü değil.
3. **Yeni karşılaştırmalar.** Churn 180 ve 365 gün için yan yana; ikili testlere Bonferroni düzeltmesi;
   sepet tablosuna destek, güven aralığı ve tüm siparişlere göre lift; tahmine başlangıç tahmininin toplamı.

## Sayı karşılaştırması

| Ölçü | v1 | Yeni | Değişim nedeni |
| --- | --- | --- | --- |
| Geçerli sipariş / müşteri | 98.197 / 94.982 | 98.197 / 94.982 | aynı |
| Ciro | R$15.738.055 | R$15.738.055 | aynı |
| RFM segment büyüklükleri (7 segment) | 1.093 … 23.045 | aynı | aynı |
| Kohort sayısı | 19 | 18 | gözlem sonu |
| Ağırlıklı tutunma 1 / 3 / 6 / 12. ay | %0,48 / 0,26 / 0,23 / 0,18 | %0,48 / 0,26 / 0,23 / 0,19 | gözlem sonu |
| 30 / 90 / 180 / 365 günde tekrar alım | %0,67 / 1,31 / 1,99 / 3,35 | %0,66 / 1,31 / 2,00 / 3,36 | gözlem sonu |
| Churn 180 gün: popülasyon / geri dönen | 52.465 / 944 | 50.232 / 898 | gözlem sonu |
| 180 günde tekrar alım (teslimattan) | %1,80 | %1,79 | gözlem sonu |
| Teslimat ≤7 gün / >21 gün | %2,05 / %1,41 (p = 0,002) | %2,04 / %1,38 (p = 0,002) | gözlem sonu |
| Yorum 5 / 1 yıldız | %1,92 / %1,54 (p = 0,08) | %1,92 / %1,49 (p = 0,050; düzeltilmiş 0,25) | gözlem sonu |
| 3+ kalem / 1 kalem | %2,68 / %1,75 (p = 0,02) | %2,54 / %1,74 (p = 0,045; düzeltilmiş 0,23) | gözlem sonu |
| Lojistik model AUC | 0,570 | 0,576 | gözlem sonu |
| Gradient boosting AUC | 0,553 | — | kaldırıldı |
| Başlangıç kuralı AUC | — | 0,552 | yeni |
| İlk desil yakalama | %14,9 | %14,6 | gözlem sonu |
| Churn 365 gün: tekrar alım / teslimat farkı | — | %3,11 / p = 0,26 (anlamlı değil) | yeni |
| Sepet: çok kategorili sipariş, çiftler | 726, 17 çift | 726, 17 çift | aynı |
| 14 hafta taban tahmin | R$3,46 milyon | R$3,46 milyon | aynı |
| Başlangıç tahmini 14 hafta | — | R$4,27 milyon | yeni |
| Black Friday çarpanı | 2,43 | 2,43 | aynı |

## Rapora etkisi

- "Teslimat hızı belirleyici" ifadesi zayıflatıldı: ilişki 180 günlük pencerede anlamlı, 365 günlük pencerede
  anlamlı değil.
- Yorum puanı ve kalem sayısı farkları çoklu karşılaştırma düzeltmesinden sonra anlamlı değil.
- Tahmin tek bir sayı olarak sunulmuyor: en iyi model ile başlangıç tahmini arasında R$0,8 milyon fark var.
