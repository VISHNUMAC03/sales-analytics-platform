"""
Step 4 - TRANSFORM with SQL.

Each .sql file in sql/<layer>/ builds exactly one table. We run the layers in
order - staging, then marts, then reporting - because each layer reads from
the one before it. Inside a layer, files run in alphabetical order; when one
table needs another from the SAME layer, a number prefix fixes the order:
01_sales_enriched.sql runs before 02_rpt_monthly_revenue.sql. The prefix is
not part of the table name.

This is the same idea dbt uses ("one model = one SQL file"), so moving this
project to dbt later is mostly copying files.
"""

import logging
import re
from pathlib import Path

import duckdb

logger = logging.getLogger(__name__)

LAYERS = ["staging", "marts", "reporting"]


def run_sql_models(con: duckdb.DuckDBPyConnection, sql_dir: Path) -> list[str]:
    built = []
    for layer in LAYERS:
        for sql_file in sorted((sql_dir / layer).glob("*.sql")):
            try:
                con.execute(sql_file.read_text(encoding="utf-8"))
            except duckdb.Error as exc:
                # Say WHICH file broke - the raw database error alone is hard to trace.
                raise RuntimeError(f"SQL model {layer}/{sql_file.name} failed: {exc}") from exc
            table = f"{layer}.{re.sub(r'^[0-9]+_', '', sql_file.stem)}"
            count = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            logger.info("Built %-38s %6d rows", table, count)
            built.append(table)
    return built
