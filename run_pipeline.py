"""Tek komutla tüm tabloları, grafikleri ve yönetici özetini yeniden üretir.

Kullanım (proje klasöründe):
    python run_pipeline.py
    python run_pipeline.py --veri-klasoru D:\\veriler\\olist
"""
import argparse
import sys
from pathlib import Path

from olist_ci import config
from olist_ci.data import VeriEksikHatasi


def main() -> int:
    ap = argparse.ArgumentParser(description="Olist müşteri ve satış analitiği hattını çalıştırır.")
    ap.add_argument("--veri-klasoru", type=Path, default=config.RAW_DIR,
                    help="Ham Olist CSV'lerinin bulunduğu klasör (varsayılan: data/raw)")
    args = ap.parse_args()

    from olist_ci import pipeline  # matplotlib vb. yalnızca gerektiğinde yüklenir

    try:
        K = pipeline.run(raw_dir=args.veri_klasoru)
    except VeriEksikHatasi as e:
        print("\nÇALIŞTIRMA DURDU: ham veri eksik.\n", file=sys.stderr)
        print(str(e), file=sys.stderr)
        return 2
    v = K["veri"]
    print("\nTamamlandı.")
    print(f"  Geçerli sipariş: {v['siparis']:,}  |  Müşteri: {v['musteri']:,}  |  Ciro: R${v['ciro']:,.0f}")
    print(f"  Tablolar : {config.TABLES_DIR}")
    print(f"  Grafikler: {config.FIGURES_DIR}")
    print(f"  Rapor    : {config.REPORTS_DIR / 'yonetici_ozeti.md'}")
    print(f"  Süre     : {K['sure_saniye']} sn")
    return 0


if __name__ == "__main__":
    sys.exit(main())
