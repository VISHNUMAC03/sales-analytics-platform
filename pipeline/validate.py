"""
Step 2 - CLEAN & VALIDATE with pandas.

Every row coming in is put into one of two buckets:
  * clean    -> goes to the warehouse
  * rejected -> saved to data/rejected/ with a human-readable reason

Two kinds of problem:
  * FIXABLE    - " usd " -> "USD", "  germany " -> "Germany", bad email -> blank.
                 We repair these and keep the row.
  * UNFIXABLE  - missing customer, quantity of -2, date "2024-02-30".
                 We cannot guess the truth, so the row is rejected.

The clean_* functions take a DataFrame and return (clean_df, rejected_df).
They never read or write files, which makes them easy to unit-test.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from pipeline.config import BASE_CURRENCY

logger = logging.getLogger(__name__)

ORDER_COLUMNS = ["order_id", "line_number", "order_date", "customer_id", "product_id",
                 "quantity", "unit_price", "discount_pct", "currency", "channel"]
CUSTOMER_COLUMNS = ["customer_id", "customer_name", "email", "country", "region",
                    "segment", "signup_date"]
PRODUCT_COLUMNS = ["product_id", "product_name", "category", "list_price_usd", "unit_cost_usd"]

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def check_columns(df: pd.DataFrame, required: list[str], entity: str) -> None:
    """Fail fast if the source changed its format (a column was renamed/removed)."""
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"{entity}: missing required columns {missing}")


def standardize_text(df: pd.DataFrame) -> pd.DataFrame:
    """Trim spaces from every value and turn empty strings into proper missing values."""
    df = df.copy()
    for col in df.columns:
        df[col] = df[col].astype("string").str.strip().replace("", pd.NA)
    return df


def split_by_rules(original: pd.DataFrame, rules: list[tuple[str, pd.Series]]
                   ) -> tuple[pd.Series, pd.DataFrame]:
    """
    Apply rules in order. A rule is (reason, boolean mask of BAD rows).
    A row is rejected with the FIRST rule it breaks.
    Returns (keep_mask, rejected rows with a 'rejection_reason' column).
    """
    reason = pd.Series(pd.NA, index=original.index, dtype="string")
    for text, bad in rules:
        bad = bad.fillna(False).astype(bool)
        reason = reason.mask(reason.isna() & bad, text)
    rejected = original.loc[reason.notna()].assign(rejection_reason=reason[reason.notna()])
    return reason.isna(), rejected


def combine(*frames: pd.DataFrame) -> pd.DataFrame:
    """Stack rejected-row tables, skipping empty ones (pandas warns about those)."""
    non_empty = [f for f in frames if not f.empty]
    return pd.concat(non_empty) if non_empty else frames[0]


def remove_duplicates(df: pd.DataFrame, key: list[str] | None = None
                      ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Drop exact duplicate rows, then rows that repeat the business key."""
    exact = df.duplicated(keep="first")
    rejected = [df[exact].assign(rejection_reason="duplicate row")]
    df = df[~exact]
    if key:
        repeated_key = df.duplicated(subset=key, keep="first")
        rejected.append(df[repeated_key].assign(rejection_reason=f"duplicate {'+'.join(key)}"))
        df = df[~repeated_key]
    return df, combine(*rejected)


# ---------------------------------------------------------------------------
# One cleaning function per dataset
# ---------------------------------------------------------------------------
def clean_products(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    check_columns(df, PRODUCT_COLUMNS, "products")
    df = standardize_text(df[PRODUCT_COLUMNS])
    df, dupes = remove_duplicates(df, key=["product_id"])

    price = pd.to_numeric(df["list_price_usd"], errors="coerce")
    cost = pd.to_numeric(df["unit_cost_usd"], errors="coerce")
    keep, rejected = split_by_rules(df, [
        ("missing product_id", df["product_id"].isna()),
        ("missing product_name", df["product_name"].isna()),
        ("missing category", df["category"].isna()),
        ("price missing or not positive", price.isna() | (price <= 0)),
        ("cost missing or negative", cost.isna() | (cost < 0)),
    ])
    clean = df[keep].assign(list_price_usd=price[keep], unit_cost_usd=cost[keep])
    return clean, combine(dupes, rejected)


def clean_customers(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    check_columns(df, CUSTOMER_COLUMNS, "customers")
    df = standardize_text(df[CUSTOMER_COLUMNS])

    # Fixable problems: tidy them up and keep the row.
    df["country"] = df["country"].str.title()
    df["region"] = df["region"].fillna("Unknown")
    df["segment"] = df["segment"].fillna("Unknown")
    bad_email = df["email"].notna() & ~df["email"].str.match(EMAIL_PATTERN).fillna(False)
    if bad_email.any():
        logger.warning("customers: blanked %d invalid email address(es)", int(bad_email.sum()))
    df.loc[bad_email, "email"] = pd.NA
    df["signup_date"] = pd.to_datetime(df["signup_date"], format="%Y-%m-%d", errors="coerce").dt.date

    # Exact duplicates first (after tidying, so "  germany " and "Germany" match).
    df, dupes = remove_duplicates(df, key=["customer_id"])

    keep, rejected = split_by_rules(df, [
        ("missing customer_id", df["customer_id"].isna()),
        ("missing customer_name", df["customer_name"].isna()),
    ])
    return df[keep], combine(dupes, rejected)


def clean_orders(df: pd.DataFrame, valid_currencies: set[str],
                 known_customers: set[str] | None = None,
                 known_products: set[str] | None = None
                 ) -> tuple[pd.DataFrame, pd.DataFrame]:
    check_columns(df, ORDER_COLUMNS, "orders")
    df = standardize_text(df[ORDER_COLUMNS])

    # Fixable problems.
    df["currency"] = df["currency"].str.upper()
    df["channel"] = df["channel"].str.title().fillna("Unknown")
    df["discount_pct"] = df["discount_pct"].fillna("0")

    df, dupes = remove_duplicates(df, key=["order_id", "line_number"])

    # Convert text to real types. Anything that can't be converted becomes missing (NaN/NaT).
    order_date = pd.to_datetime(df["order_date"], format="%Y-%m-%d", errors="coerce")
    line_number = pd.to_numeric(df["line_number"], errors="coerce")
    quantity = pd.to_numeric(df["quantity"], errors="coerce")
    unit_price = pd.to_numeric(df["unit_price"], errors="coerce")
    discount = pd.to_numeric(df["discount_pct"], errors="coerce")

    rules = [
        ("missing order_id", df["order_id"].isna()),
        ("invalid line_number", line_number.isna() | (line_number < 1)),
        ("missing or invalid order_date", order_date.isna()),
        ("missing customer_id", df["customer_id"].isna()),
        ("missing product_id", df["product_id"].isna()),
        ("quantity must be a positive whole number",
         quantity.isna() | (quantity <= 0) | (quantity % 1 != 0)),
        ("unit_price missing or negative", unit_price.isna() | (unit_price < 0)),
        ("discount_pct must be between 0 and 1", discount.isna() | (discount < 0) | (discount >= 1)),
        ("unknown currency", ~df["currency"].isin(valid_currencies)),
    ]
    # Referential checks: an order must point to a customer/product we actually know.
    if known_customers is not None:
        rules.append(("unknown customer_id",
                      df["customer_id"].notna() & ~df["customer_id"].isin(known_customers)))
    if known_products is not None:
        rules.append(("unknown product_id",
                      df["product_id"].notna() & ~df["product_id"].isin(known_products)))

    keep, rejected = split_by_rules(df, rules)
    clean = df[keep].assign(
        order_date=order_date[keep].dt.date,
        line_number=line_number[keep].astype(int),
        quantity=quantity[keep].astype(int),
        unit_price=unit_price[keep],
        discount_pct=discount[keep],
    )
    return clean, combine(dupes, rejected)


def parse_fx_rates(payload: dict) -> pd.DataFrame:
    """Turn the API's JSON into a table: currency | rate_per_usd | rate_date."""
    if payload.get("base") != BASE_CURRENCY:
        raise ValueError(f"Expected rates based on {BASE_CURRENCY}, got {payload.get('base')}")
    rates = {BASE_CURRENCY: 1.0, **payload["rates"]}
    df = pd.DataFrame({"currency": list(rates), "rate_per_usd": list(rates.values())})
    df["rate_per_usd"] = pd.to_numeric(df["rate_per_usd"], errors="coerce")
    if df["rate_per_usd"].isna().any() or (df["rate_per_usd"] <= 0).any():
        raise ValueError(f"Exchange rates contain invalid values: {rates}")
    df["rate_date"] = payload.get("date")
    return df


# ---------------------------------------------------------------------------
# Run everything and write the results to disk
# ---------------------------------------------------------------------------
@dataclass
class ValidationResult:
    summary: list[dict] = field(default_factory=list)        # one row per entity
    rejected: pd.DataFrame = field(default_factory=pd.DataFrame)


def _rejected_as_records(entity: str, rejected: pd.DataFrame) -> pd.DataFrame:
    """Store rejected rows of any shape in one table: entity | reason | record (JSON)."""
    if rejected.empty:
        return pd.DataFrame(columns=["entity", "rejection_reason", "record"])
    data = rejected.drop(columns="rejection_reason").astype(object)
    data = data.where(data.notna(), None)
    records = [json.dumps(row, default=str) for row in data.to_dict(orient="records")]
    return pd.DataFrame({"entity": entity,
                         "rejection_reason": rejected["rejection_reason"].astype(str).values,
                         "record": records})


def validate_sources(landed: dict[str, Path], fx_path: Path,
                     clean_dir: Path, rejected_dir: Path) -> ValidationResult:
    clean_dir.mkdir(parents=True, exist_ok=True)
    rejected_dir.mkdir(parents=True, exist_ok=True)
    result = ValidationResult()
    all_rejected = []

    def read(entity: str) -> pd.DataFrame:
        # dtype=str: read everything as text first; WE decide the types, not pandas' guesses.
        return pd.read_csv(landed[entity], dtype=str, keep_default_na=False)

    fx = parse_fx_rates(json.loads(fx_path.read_text(encoding="utf-8")))
    fx.to_csv(clean_dir / "fx_rates.csv", index=False)

    products_raw = read("products")
    products, rejected_products = clean_products(products_raw)
    customers_raw = read("customers")
    customers, rejected_customers = clean_customers(customers_raw)
    orders_raw = read("orders")
    orders, rejected_orders = clean_orders(
        orders_raw,
        valid_currencies=set(fx["currency"]),
        known_customers=set(customers["customer_id"]),
        known_products=set(products["product_id"]),
    )

    for entity, raw, clean, rejected in [
        ("products", products_raw, products, rejected_products),
        ("customers", customers_raw, customers, rejected_customers),
        ("orders", orders_raw, orders, rejected_orders),
    ]:
        clean.to_csv(clean_dir / f"{entity}.csv", index=False)
        rejected.to_csv(rejected_dir / f"{entity}_rejected.csv", index=False)
        all_rejected.append(_rejected_as_records(entity, rejected))
        result.summary.append({"entity": entity, "input_rows": len(raw),
                               "clean_rows": len(clean), "rejected_rows": len(rejected)})
        logger.info("Validated %-9s: %5d in -> %5d clean, %4d rejected",
                    entity, len(raw), len(clean), len(rejected))
        for reason, count in rejected["rejection_reason"].value_counts().items():
            logger.info("    rejected %4d %s: %s", count, entity, reason)

    result.rejected = combine(*all_rejected).reset_index(drop=True)
    return result
