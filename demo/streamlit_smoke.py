from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_streamlit_demo_starts_without_model_or_data():
    app_path = Path(__file__).resolve().parents[1] / "demo" / "app.py"
    app = AppTest.from_file(str(app_path)).run(timeout=30)

    assert not app.exception
    assert app.title[0].value == "TerraSpectra"
    assert len(app.file_uploader) == 2
    assert any("trusted model bundle" in item.value.lower() for item in app.warning)
    assert any("not a disease forecast" in item.value.lower() for item in app.info)
