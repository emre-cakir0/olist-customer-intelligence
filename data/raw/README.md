# Ham veri (bu klasöre koyun, Git'e eklenmez)

Kaynak: **Brazilian E-Commerce Public Dataset by Olist**, Kaggle: <https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce>
(lisans: CC BY-NC-SA 4.0; ticari olmayan kullanım).

## Edinme adımları (Windows)

1. Kaggle'a giriş yapın, yukarıdaki sayfada **Download** düğmesine basın (`archive.zip`, yaklaşık 45 MB).
2. ZIP'i açın ve aşağıdaki 7 dosyayı bu klasöre (`data\raw`) kopyalayın:

| Dosya | Satır (beklenen) |
| --- | --- |
| `olist_orders_dataset.csv` | 99.441 |
| `olist_customers_dataset.csv` | 99.441 |
| `olist_order_items_dataset.csv` | 112.650 |
| `olist_order_payments_dataset.csv` | 103.886 |
| `olist_order_reviews_dataset.csv` | 99.224 |
| `olist_products_dataset.csv` | 32.951 |
| `product_category_name_translation.csv` | 71 |

`olist_geolocation_dataset.csv` ve `olist_sellers_dataset.csv` kullanılmaz; klasörde durmaları sorun olmaz.

İsteğe bağlı, Kaggle komut satırı aracıyla (API anahtarı `%USERPROFILE%\.kaggle\kaggle.json` içinde olmalı):

```powershell
pip install kaggle
kaggle datasets download -d olistbr/brazilian-ecommerce -p data\raw --unzip
```

Dosyalar başka bir klasördeyse: `python run_pipeline.py --veri-klasoru D:\veriler\olist`

Dosyalardan biri eksikse `run_pipeline.py` hangi dosyaların eksik olduğunu yazar ve 2 çıkış koduyla durur;
gerçek veri testleri atlanır.
