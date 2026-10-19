"""
End-to-end test: generate data, run the WHOLE pipeline into a temporary
folder, and check the warehouse looks right. Uses --offline rates so it never
depends on the internet.
"""

import duckdb
import pytest

from pipeline.run_pipeline import run
from scripts.generate_sample_data import generate


@pytest.fixture(scope="module")
def warehouse(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("pipeline")
    generate(tmp / "data" / "source")
    wh_path = tmp / "warehouse.duckdb"
    run_id = run(offline=True, data_dir=tmp / "data", warehouse_path=wh_path)
    con = duckdb.connect(str(wh_path), read_only=True)
    yield con, run_id
    con.close()


def test_run_is_recorded_as_success(warehouse):
    con, run_id = warehouse
    status = con.execute("SELECT status FROM meta.pipeline_runs WHERE run_id = ?",
                         [run_id]).fetchone()[0]
    assert status == "success"


def test_all_quality_checks_pass(warehouse):
    con, run_id = warehouse
    failed = con.execute("SELECT COUNT(*) FROM meta.quality_results "
                         "WHERE run_id = ? AND status = 'fail'", [run_id]).fetchone()[0]
    assert failed == 0


def test_bad_rows_were_rejected_not_loaded(warehouse):
    con, _ = warehouse
    rejected = con.execute("SELECT COUNT(*) FROM raw.rejected_records").fetchone()[0]
    assert rejected > 0
    unknown = con.execute("SELECT COUNT(*) FROM marts.fct_sales "
                          "WHERE product_id = 'P999' OR currency = 'XYZ'").fetchone()[0]
    assert unknown == 0


def test_star_schema_tables_have_rows(warehouse):
    con, _ = warehouse
    for table in ["marts.fct_sales", "marts.dim_customers", "marts.dim_products",
                  "marts.dim_date", "reporting.sales_enriched"]:
        assert con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] > 0, table
