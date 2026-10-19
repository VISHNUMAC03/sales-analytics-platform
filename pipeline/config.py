"""
Central place for settings.

Every other module imports paths and options from here, so if you want to move
the warehouse or change the API, you change ONE file (or set an environment
variable in a .env file - see .env.example).
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Folder that contains this repository (one level above pipeline/)
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Read optional settings from a .env file in the project root.
load_dotenv(PROJECT_ROOT / ".env")

# ---- Folders ---------------------------------------------------------------
DATA_DIR = Path(os.getenv("DATA_DIR", PROJECT_ROOT / "data"))
# Inside DATA_DIR the pipeline uses:
#   source/    files "delivered" by the sales system (our input)
#   raw/       exact copies of every input, stored per run (our local "S3")
#   clean/     validated data, ready for the warehouse
#   rejected/  rows that failed validation, with the reason

WAREHOUSE_PATH = Path(os.getenv("WAREHOUSE_PATH", PROJECT_ROOT / "warehouse" / "sales.duckdb"))
LOG_DIR = Path(os.getenv("LOG_DIR", PROJECT_ROOT / "logs"))
SQL_DIR = PROJECT_ROOT / "sql"

# ---- Exchange-rate API -------------------------------------------------------
# Frankfurter is a free, open-source currency API that needs no API key.
FX_API_URL = os.getenv("FX_API_URL", "https://api.frankfurter.app/latest")
BASE_CURRENCY = "USD"
SUPPORTED_CURRENCIES = ["USD", "CAD", "GBP", "EUR", "INR", "AUD", "JPY"]

# ---- Optional cloud storage --------------------------------------------------
# Leave empty to keep raw files on your computer only.
# Set S3_BUCKET (and AWS credentials) to ALSO upload raw files to Amazon S3.
S3_BUCKET = os.getenv("S3_BUCKET") or None
