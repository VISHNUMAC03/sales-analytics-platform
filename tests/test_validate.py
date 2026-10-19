"""
Unit tests for the cleaning rules. Run with:  pytest

Each test builds a tiny DataFrame by hand, runs one cleaning function, and
checks the result. If someone later breaks a rule, the test fails and tells them.
"""

import pandas as pd
import pytest

from pipeline.validate import (clean_customers, clean_orders, clean_products,
                               parse_fx_rates)

CURRENCIES = {"USD", "EUR"}


def order(**overrides) -> dict:
    """One valid order line; tests change only the field they care about."""
    row = {"order_id": "SO-1", "line_number": "1", "order_date": "2024-05-01",
           "customer_id": "C0001", "product_id": "P001", "quantity": "2",
           "unit_price": "10.00", "discount_pct": "0", "currency": "USD", "channel": "Online"}
    row.update(overrides)
    return row


def run_orders(*rows, **kwargs):
    return clean_orders(pd.DataFrame(list(rows)), CURRENCIES, **kwargs)


def test_valid_order_is_kept_with_proper_types():
    clean, rejected = run_orders(order())
    assert len(clean) == 1 and rejected.empty
    assert clean["quantity"].iloc[0] == 2
    assert clean["unit_price"].iloc[0] == 10.0


def test_exact_duplicates_are_removed():
    clean, rejected = run_orders(order(), order())
    assert len(clean) == 1
    assert rejected["rejection_reason"].tolist() == ["duplicate row"]


def test_same_order_line_with_different_values_is_rejected():
    clean, rejected = run_orders(order(), order(quantity="5"))
    assert len(clean) == 1
    assert rejected["rejection_reason"].iloc[0] == "duplicate order_id+line_number"


@pytest.mark.parametrize("bad_date", ["2024-02-30", "31/12/2024", "not available", ""])
def test_invalid_dates_are_rejected(bad_date):
    clean, rejected = run_orders(order(order_date=bad_date))
    assert clean.empty
    assert rejected["rejection_reason"].iloc[0] == "missing or invalid order_date"


@pytest.mark.parametrize("bad_qty", ["0", "-2", "1.5", "abc"])
def test_quantity_must_be_positive_whole_number(bad_qty):
    clean, rejected = run_orders(order(quantity=bad_qty))
    assert clean.empty
    assert "quantity" in rejected["rejection_reason"].iloc[0]


def test_missing_customer_is_rejected():
    clean, rejected = run_orders(order(customer_id="  "))
    assert rejected["rejection_reason"].iloc[0] == "missing customer_id"


def test_messy_currency_is_fixed_not_rejected():
    clean, rejected = run_orders(order(currency=" usd "))
    assert rejected.empty
    assert clean["currency"].iloc[0] == "USD"


def test_unknown_currency_is_rejected():
    _, rejected = run_orders(order(currency="XYZ"))
    assert rejected["rejection_reason"].iloc[0] == "unknown currency"


def test_discount_over_100_percent_is_rejected():
    _, rejected = run_orders(order(discount_pct="1.5"))
    assert "discount" in rejected["rejection_reason"].iloc[0]


def test_unknown_customer_and_product_are_rejected():
    _, rejected = run_orders(order(order_id="SO-1", customer_id="C9999"),
                             order(order_id="SO-2", product_id="P999"),
                             known_customers={"C0001"}, known_products={"P001"})
    assert rejected["rejection_reason"].tolist() == ["unknown customer_id", "unknown product_id"]


def test_first_broken_rule_is_reported():
    _, rejected = run_orders(order(order_date="bad", quantity="-1"))
    assert rejected["rejection_reason"].iloc[0] == "missing or invalid order_date"


def test_missing_column_fails_fast():
    df = pd.DataFrame([order()]).drop(columns="currency")
    with pytest.raises(ValueError, match="currency"):
        clean_orders(df, CURRENCIES)


def test_customers_invalid_email_is_blanked_and_country_tidied():
    df = pd.DataFrame([{"customer_id": "C1", "customer_name": "Ann Lee", "email": "ann at x.com",
                        "country": "  germany ", "region": "Europe", "segment": "Consumer",
                        "signup_date": "2024-01-01"}])
    clean, rejected = clean_customers(df)
    assert rejected.empty
    assert pd.isna(clean["email"].iloc[0])
    assert clean["country"].iloc[0] == "Germany"


def test_customers_without_id_are_rejected():
    df = pd.DataFrame([{"customer_id": "", "customer_name": "Ghost", "email": "",
                        "country": "Spain", "region": "Europe", "segment": "Consumer",
                        "signup_date": "2024-01-01"}])
    clean, rejected = clean_customers(df)
    assert clean.empty and rejected["rejection_reason"].iloc[0] == "missing customer_id"


def test_products_with_negative_price_are_rejected():
    df = pd.DataFrame([{"product_id": "P1", "product_name": "Thing", "category": "Sports",
                        "list_price_usd": "-10", "unit_cost_usd": "5"}])
    clean, rejected = clean_products(df)
    assert clean.empty and "price" in rejected["rejection_reason"].iloc[0]


def test_fx_rates_include_base_currency():
    df = parse_fx_rates({"base": "USD", "date": "2025-01-01", "rates": {"EUR": 0.9}})
    assert dict(zip(df["currency"], df["rate_per_usd"])) == {"USD": 1.0, "EUR": 0.9}


def test_fx_rates_reject_wrong_base_or_bad_values():
    with pytest.raises(ValueError):
        parse_fx_rates({"base": "EUR", "rates": {"USD": 1.1}})
    with pytest.raises(ValueError):
        parse_fx_rates({"base": "USD", "rates": {"EUR": -1}})
