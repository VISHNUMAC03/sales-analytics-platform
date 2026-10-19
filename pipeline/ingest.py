"""
Step 1 - INGEST: collect data from its sources and land it in raw storage.

Two kinds of source, just like a real company:
  * CSV files exported by the sales system (orders, customers, products)
  * a web API (live currency exchange rates), because orders arrive in
    7 currencies and the business wants every number in US dollars.

This is the job tools like Fivetran or Airbyte do in the architecture diagram.
"""

import json
import logging
import time
from pathlib import Path

import requests

from pipeline.config import BASE_CURRENCY, SUPPORTED_CURRENCIES
from pipeline.storage import land_file, land_json

logger = logging.getLogger(__name__)

SOURCE_FILES = {
    "orders": "orders.csv",
    "customers": "customers.csv",
    "products": "products.csv",
}
FX_FALLBACK_FILE = "fx_rates_fallback.json"


def ingest_csv_files(source_dir: Path, raw_dir: Path, run_id: str) -> dict[str, Path]:
    """Copy each source CSV into the raw zone. Returns {entity: landed path}."""
    landed = {}
    for entity, filename in SOURCE_FILES.items():
        src = source_dir / filename
        if not src.exists():
            raise FileNotFoundError(
                f"Source file {src} not found. Run: python scripts/generate_sample_data.py"
            )
        landed[entity] = land_file(src, raw_dir, entity, run_id)
        logger.info("Ingested %s -> %s", filename, landed[entity])
    return landed


def fetch_fx_rates(api_url: str, retries: int = 3, timeout: int = 10) -> dict:
    """Call the exchange-rate API. Retries a few times because networks are flaky."""
    params = {"from": BASE_CURRENCY,
              "to": ",".join(c for c in SUPPORTED_CURRENCIES if c != BASE_CURRENCY)}
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(api_url, params=params, timeout=timeout)
            response.raise_for_status()          # turn HTTP 4xx/5xx into an error
            payload = response.json()
            if "rates" not in payload:
                raise ValueError(f"Unexpected API response: {payload}")
            return payload
        except (requests.RequestException, ValueError) as exc:
            logger.warning("FX API attempt %d/%d failed: %s", attempt, retries, exc)
            if attempt < retries:
                time.sleep(2 * attempt)          # wait a little longer each time
    raise ConnectionError(f"FX API unavailable after {retries} attempts")


def ingest_fx_rates(source_dir: Path, raw_dir: Path, run_id: str,
                    api_url: str, offline: bool = False) -> Path:
    """Get exchange rates from the API (or the fallback file) and land them."""
    payload = None
    if offline:
        logger.info("Offline mode: using fallback exchange rates")
    else:
        try:
            payload = fetch_fx_rates(api_url)
            logger.info("Fetched live exchange rates dated %s", payload.get("date"))
        except ConnectionError as exc:
            logger.warning("%s - falling back to %s", exc, FX_FALLBACK_FILE)

    if payload is None:
        payload = json.loads((source_dir / FX_FALLBACK_FILE).read_text(encoding="utf-8"))

    path = land_json(payload, raw_dir, "fx_rates", run_id, "fx_rates.json")
    logger.info("Ingested exchange rates -> %s", path)
    return path
