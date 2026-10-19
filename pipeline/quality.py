"""
Step 5 - DATA QUALITY CHECKS on the finished warehouse tables.

Python validation (step 2) checks individual input rows. These checks look at
the finished model as a whole: Is every sale line unique? Does every sale point
to a real customer? Does the reporting layer add up to the fact table?

Convention (borrowed from dbt): every file in sql/tests/ is a query that
returns the BAD rows. Zero rows = pass. Any rows = fail.

This is the job Monte Carlo does in the architecture diagram.
"""

import logging
from datetime import datetime
from pathlib import Path

import duckdb

logger = logging.getLogger(__name__)


class DataQualityError(Exception):
    """Raised when one or more data quality checks fail."""


def run_quality_checks(con: duckdb.DuckDBPyConnection, tests_dir: Path, run_id: str) -> list[dict]:
    results = []
    for sql_file in sorted(tests_dir.glob("*.sql")):
        query = sql_file.read_text(encoding="utf-8").strip().rstrip(";")
        failing = con.execute(f"SELECT COUNT(*) FROM ({query}) AS failures").fetchone()[0]
        status = "pass" if failing == 0 else "fail"
        results.append({"check_name": sql_file.stem, "status": status, "failing_rows": failing})
        con.execute("INSERT INTO meta.quality_results VALUES (?, ?, ?, ?, ?)",
                    [run_id, sql_file.stem, status, failing, datetime.now()])
        if status == "pass":
            logger.info("PASS  %s", sql_file.stem)
        else:
            logger.error("FAIL  %s (%d failing rows)", sql_file.stem, failing)

    failed = [r["check_name"] for r in results if r["status"] == "fail"]
    if failed:
        raise DataQualityError(f"{len(failed)} quality check(s) failed: {', '.join(failed)}")
    logger.info("All %d quality checks passed", len(results))
    return results
