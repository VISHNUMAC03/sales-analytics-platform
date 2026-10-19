"""
Smoke test for the dashboard: build a warehouse, run the Streamlit app
without a browser (Streamlit's AppTest), and make sure no error is raised.
"""

from streamlit.testing.v1 import AppTest

from pipeline import config
from pipeline.run_pipeline import run
from scripts.generate_sample_data import generate


def test_dashboard_renders_without_errors(tmp_path, monkeypatch):
    generate(tmp_path / "data" / "source")
    wh_path = tmp_path / "warehouse.duckdb"
    run(offline=True, data_dir=tmp_path / "data", warehouse_path=wh_path)

    # Point the dashboard at the temporary warehouse.
    monkeypatch.setattr(config, "WAREHOUSE_PATH", wh_path)
    app = AppTest.from_file("dashboard/app.py", default_timeout=60).run()

    assert not app.exception, app.exception
    assert app.title[0].value == "Sales Analytics"
    assert len(app.metric) == 6
