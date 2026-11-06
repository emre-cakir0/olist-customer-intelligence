"""Panel duman testi: Streamlit kuruluysa ve hat çıktıları varsa panel hatasız açılıyor mu?"""
import pytest

from olist_ci import config, data

st = pytest.importorskip("streamlit")


@pytest.mark.skipif(not data.processed_available() or not (config.TABLES_DIR / "sonuclar.json").is_file(),
                    reason="Önce `python run_pipeline.py` çalıştırın.")
def test_panel_hatasiz_acilir():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(config.ROOT / "app" / "panel.py"), default_timeout=120).run()
    assert not at.exception, at.exception
    assert any("Olist" in t.value for t in at.title)
