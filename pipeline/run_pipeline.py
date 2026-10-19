"""
The ORCHESTRATOR: runs every step in order, logs everything, records the outcome.

    python -m pipeline.run_pipeline            # normal run (calls the live FX API)
    python -m pipeline.run_pipeline --offline  # no internet needed

Exit code 0 = success, 1 = failure. Docker, cron, Airflow and GitHub Actions all
use the exit code to decide whether a job worked, so getting it right matters.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from pipeline import config
from pipeline.ingest import ingest_csv_files, ingest_fx_rates
from pipeline.logger import setup_logging
from pipeline.quality import run_quality_checks
from pipeline.transform import run_sql_models
from pipeline.validate import validate_sources
from pipeline.warehouse import (connect, load_clean_files, load_rejected, record_run,
                                record_validation_summary)

logger = logging.getLogger("pipeline")


def run(offline: bool = False, data_dir: Path = config.DATA_DIR,
        warehouse_path: Path = config.WAREHOUSE_PATH) -> str:
    """Run the whole pipeline once. Returns the run_id. Raises on failure."""
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    started_at = datetime.now()
    source_dir, raw_dir = data_dir / "source", data_dir / "raw"
    clean_dir, rejected_dir = data_dir / "clean", data_dir / "rejected"

    logger.info("=" * 60)
    logger.info("Pipeline run %s started", run_id)
    con = None
    try:
        logger.info("--- Step 1/5: ingest ---")
        landed = ingest_csv_files(source_dir, raw_dir, run_id)
        fx_path = ingest_fx_rates(source_dir, raw_dir, run_id, config.FX_API_URL, offline)

        logger.info("--- Step 2/5: clean & validate ---")
        validation = validate_sources(landed, fx_path, clean_dir, rejected_dir)

        logger.info("--- Step 3/5: load warehouse ---")
        con = connect(warehouse_path)
        load_clean_files(con, clean_dir)
        load_rejected(con, validation.rejected, run_id)
        record_validation_summary(con, run_id, validation.summary)

        logger.info("--- Step 4/5: transform (SQL models) ---")
        run_sql_models(con, config.SQL_DIR)

        logger.info("--- Step 5/5: data quality checks ---")
        run_quality_checks(con, config.SQL_DIR / "tests", run_id)

        record_run(con, run_id, started_at, "success")
        logger.info("Pipeline run %s finished successfully", run_id)
        return run_id

    except Exception as exc:
        # logger.exception also writes the full traceback to logs/pipeline.log
        logger.exception("Pipeline run %s FAILED: %s", run_id, exc)
        try:
            con = con or connect(warehouse_path)
            record_run(con, run_id, started_at, "failed", str(exc))
        except Exception:
            logger.exception("Could not record the failed run in the warehouse")
        raise
    finally:
        if con is not None:
            con.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the sales analytics pipeline")
    parser.add_argument("--offline", action="store_true",
                        help="use fallback exchange rates instead of calling the API")
    args = parser.parse_args(argv)

    log_file = setup_logging(config.LOG_DIR)
    logger.info("Logging to %s", log_file)
    try:
        run(offline=args.offline)
    except Exception:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
