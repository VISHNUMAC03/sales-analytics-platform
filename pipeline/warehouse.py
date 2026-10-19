"""
Step 3 - LOAD into the data warehouse.

We use DuckDB: a free analytical database that lives in a single file
(warehouse/sales.duckdb). It speaks standard SQL, so everything you learn here
transfers to Snowflake, BigQuery or Redshift.

The warehouse is organised into schemas (think "folders for tables"):
  raw        validated data exactly as loaded from data/clean/
  staging    typed and renamed copies of raw tables          (sql/staging)
  marts      the star schema: facts and dimensions            (sql/marts)
  reporting  ready-to-chart tables for the dashboard          (sql/reporting)
  meta       pipeline bookkeeping: runs, validation, test results
"""

import logging
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd

logger = logging.getLogger(__name__)

SCHEMAS = ["raw", "staging", "marts", "reporting", "meta"]
CLEAN_TABLES = ["orders", "customers", "products", "fx_rates"]


def connect(warehouse_path: Path) -> duckdb.DuckDBPyConnection:
    warehouse_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(warehouse_path))
    for schema in SCHEMAS:
        con.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
    con.execute("""
        CREATE TABLE IF NOT EXISTS meta.pipeline_runs (
            run_id VARCHAR, started_at TIMESTAMP, finished_at TIMESTAMP,
            status VARCHAR, error_message VARCHAR, fact_rows BIGINT)
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS meta.validation_summary (
            run_id VARCHAR, entity VARCHAR, input_rows BIGINT,
            clean_rows BIGINT, rejected_rows BIGINT)
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS meta.quality_results (
            run_id VARCHAR, check_name VARCHAR, status VARCHAR,
            failing_rows BIGINT, checked_at TIMESTAMP)
    """)
    return con


def load_clean_files(con: duckdb.DuckDBPyConnection, clean_dir: Path) -> None:
    """Full refresh: replace each raw table with the latest clean file.

    "CREATE OR REPLACE" makes the load idempotent - running it twice gives the
    same result as running it once, so re-running after a failure is safe.
    """
    for table in CLEAN_TABLES:
        path = (clean_dir / f"{table}.csv").as_posix().replace("'", "''")
        con.execute(f"CREATE OR REPLACE TABLE raw.{table} AS "
                    f"SELECT * FROM read_csv('{path}', header = true, auto_detect = true)")
        count = con.execute(f"SELECT COUNT(*) FROM raw.{table}").fetchone()[0]
        logger.info("Loaded raw.%-10s %6d rows", table, count)


def load_rejected(con: duckdb.DuckDBPyConnection, rejected: pd.DataFrame, run_id: str) -> None:
    df = rejected.assign(run_id=run_id)
    con.register("rejected_df", df)
    con.execute("CREATE OR REPLACE TABLE raw.rejected_records AS "
                "SELECT run_id, entity, rejection_reason, record FROM rejected_df")
    con.unregister("rejected_df")
    logger.info("Loaded raw.rejected_records %d rows", len(df))


def record_validation_summary(con: duckdb.DuckDBPyConnection, run_id: str,
                              summary: list[dict]) -> None:
    for row in summary:
        con.execute("INSERT INTO meta.validation_summary VALUES (?, ?, ?, ?, ?)",
                    [run_id, row["entity"], row["input_rows"], row["clean_rows"],
                     row["rejected_rows"]])


def record_run(con: duckdb.DuckDBPyConnection, run_id: str, started_at: datetime,
               status: str, error_message: str | None = None) -> None:
    fact_rows = None
    if status == "success":
        fact_rows = con.execute("SELECT COUNT(*) FROM marts.fct_sales").fetchone()[0]
    con.execute("INSERT INTO meta.pipeline_runs VALUES (?, ?, ?, ?, ?, ?)",
                [run_id, started_at, datetime.now(), status, error_message, fact_rows])
