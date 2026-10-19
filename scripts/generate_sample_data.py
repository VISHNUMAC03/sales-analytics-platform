"""
Generate a realistic (but fake) retail sales dataset.

Why generate data instead of downloading it?
- It is free, needs no account, and is identical on every computer (fixed random seed).
- We deliberately inject the kind of mess real exports contain (missing IDs,
  duplicates, impossible dates, bad currencies...) so the pipeline has
  something real to clean and validate.

Output (written to data/source/ by default):
    customers.csv         ~300 customers
    products.csv          ~30 products
    orders.csv            ~5,600 order lines over 2024-2025
    fx_rates_fallback.json  exchange rates used if the live API is unreachable

Run it with:
    python scripts/generate_sample_data.py
"""

from __future__ import annotations

import csv
import json
import random
import sys
from datetime import date, timedelta
from pathlib import Path

SEED = 42
DEFAULT_OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "source"

# country -> (region, currency)
COUNTRIES = {
    "United States": ("North America", "USD"),
    "Canada": ("North America", "CAD"),
    "United Kingdom": ("Europe", "GBP"),
    "Germany": ("Europe", "EUR"),
    "France": ("Europe", "EUR"),
    "Spain": ("Europe", "EUR"),
    "India": ("Asia Pacific", "INR"),
    "Australia": ("Asia Pacific", "AUD"),
    "Japan": ("Asia Pacific", "JPY"),
}
COUNTRY_WEIGHTS = [30, 8, 12, 10, 7, 5, 12, 8, 8]

# How many units of each currency 1 USD buys (used to price orders in local currency).
GENERATION_FX = {
    "USD": 1.0, "CAD": 1.37, "GBP": 0.76, "EUR": 0.90,
    "INR": 84.0, "AUD": 1.52, "JPY": 150.0,
}

# (name, category, list price in USD)
PRODUCTS = [
    ("Wireless Mouse", "Electronics", 25), ("Mechanical Keyboard", "Electronics", 89),
    ("27-inch Monitor", "Electronics", 279), ("USB-C Hub", "Electronics", 45),
    ("Noise-Cancelling Headphones", "Electronics", 199), ("HD Webcam", "Electronics", 69),
    ("Portable SSD 1TB", "Electronics", 119), ("Bluetooth Speaker", "Electronics", 59),
    ("Ergonomic Office Chair", "Furniture", 249), ("Standing Desk", "Furniture", 499),
    ("Bookshelf", "Furniture", 129), ("Desk Lamp", "Furniture", 39),
    ("Filing Cabinet", "Furniture", 159), ("Monitor Arm", "Furniture", 79),
    ("Notebook 5-Pack", "Office Supplies", 12), ("Gel Pens 12-Pack", "Office Supplies", 9),
    ("Stapler", "Office Supplies", 15), ("Printer Paper 500 Sheets", "Office Supplies", 8),
    ("Whiteboard", "Office Supplies", 49), ("Desk Organizer", "Office Supplies", 22),
    ("Running Shoes", "Clothing", 95), ("Rain Jacket", "Clothing", 120),
    ("Cotton T-Shirt", "Clothing", 18), ("Wool Sweater", "Clothing", 70),
    ("Baseball Cap", "Clothing", 22), ("Yoga Mat", "Sports", 30),
    ("Dumbbell Set", "Sports", 85), ("Water Bottle", "Sports", 19),
    ("Fitness Tracker", "Sports", 129), ("Tennis Racket", "Sports", 110),
]

FIRST_NAMES = [
    "Aarav", "Olivia", "Liam", "Emma", "Noah", "Ava", "Sophia", "Lucas", "Mia", "Ethan",
    "Isabella", "Mateo", "Priya", "Hiro", "Yuki", "Chloe", "Leon", "Hannah", "Arjun", "Zoe",
    "Oscar", "Lea", "Diego", "Sara", "Kenji", "Amelia", "Rohan", "Grace", "Felix", "Ananya",
]
LAST_NAMES = [
    "Smith", "Patel", "Garcia", "Muller", "Martin", "Brown", "Tanaka", "Wilson", "Kumar",
    "Lopez", "Schmidt", "Dubois", "Taylor", "Sato", "Singh", "Clark", "Fischer", "Moreau",
    "Lee", "Walker", "Reddy", "Hughes", "Suzuki", "Wagner", "Bernard",
]
SEGMENTS = ["Consumer", "Corporate", "Small Business"]
SEGMENT_WEIGHTS = [60, 25, 15]

# Seasonality: shoppers buy more in November/December, less in January.
MONTH_FACTOR = {1: 0.8, 2: 0.9, 3: 1.0, 4: 1.0, 5: 1.0, 6: 0.95, 7: 0.95,
                8: 1.0, 9: 1.05, 10: 1.1, 11: 1.4, 12: 1.7}

START_DATE = date(2024, 1, 1)
END_DATE = date(2025, 12, 31)
N_CUSTOMERS = 300
N_ORDERS = 3200


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def make_products(rng: random.Random) -> list[dict]:
    rows = []
    for i, (name, category, price) in enumerate(PRODUCTS, start=1):
        rows.append({
            "product_id": f"P{i:03d}",
            "product_name": name,
            "category": category,
            "list_price_usd": f"{price:.2f}",
            "unit_cost_usd": f"{price * rng.uniform(0.45, 0.70):.2f}",
        })
    # --- deliberate data problems ---
    rows.append(dict(rows[4]))                       # exact duplicate row
    rows.append({"product_id": "P031", "product_name": "Mystery Item", "category": "Electronics",
                 "list_price_usd": "-10.00", "unit_cost_usd": "5.00"})   # negative price
    rows.append({"product_id": "P032", "product_name": "", "category": "Sports",
                 "list_price_usd": "40.00", "unit_cost_usd": "20.00"})   # missing name
    return rows


def make_customers(rng: random.Random) -> list[dict]:
    rows = []
    span = (date(2025, 6, 30) - date(2023, 1, 1)).days
    for i in range(1, N_CUSTOMERS + 1):
        first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
        country = rng.choices(list(COUNTRIES), weights=COUNTRY_WEIGHTS)[0]
        rows.append({
            "customer_id": f"C{i:04d}",
            "customer_name": f"{first} {last}",
            "email": f"{first.lower()}.{last.lower()}{i}@example.com",
            "country": country,
            "region": COUNTRIES[country][0],
            "segment": rng.choices(SEGMENTS, weights=SEGMENT_WEIGHTS)[0],
            "signup_date": (date(2023, 1, 1) + timedelta(days=rng.randint(0, span))).isoformat(),
        })
    # --- deliberate data problems ---
    for idx in rng.sample(range(N_CUSTOMERS), 5):
        rows[idx]["email"] = rows[idx]["email"].replace("@", " at ")   # invalid email
    for idx in rng.sample(range(N_CUSTOMERS), 4):
        rows[idx]["country"] = f"  {rows[idx]['country'].lower()} "    # messy casing/spaces
    for idx in rng.sample(range(N_CUSTOMERS), 3):
        rows.append(dict(rows[idx]))                                   # duplicate customers
    rows.append({"customer_id": "", "customer_name": "Ghost Customer", "email": "",
                 "country": "Germany", "region": "Europe", "segment": "Consumer",
                 "signup_date": "2024-03-01"})                         # missing ID
    return rows


def make_orders(rng: random.Random, customers: list[dict], n_products: int) -> list[dict]:
    days = [START_DATE + timedelta(days=d) for d in range((END_DATE - START_DATE).days + 1)]
    total = len(days)
    # Weight each day by growth over time and by seasonality.
    day_weights = [(1 + 0.35 * i / total) * MONTH_FACTOR[d.month] for i, d in enumerate(days)]
    order_dates = sorted(rng.choices(days, weights=day_weights, k=N_ORDERS))

    real_customers = customers[:N_CUSTOMERS]
    # A few customers buy a lot, most buy a little (like real life).
    customer_weights = [rng.paretovariate(1.5) for _ in real_customers]
    # Cheap products sell more often than expensive ones.
    product_weights = [1 / (price ** 0.5) for _, _, price in PRODUCTS]

    rows = []
    for n, order_date in enumerate(order_dates, start=1):
        customer = rng.choices(real_customers, weights=customer_weights)[0]
        currency = COUNTRIES[customer["country"].strip().title()][1]  # undo the messy casing
        channel = rng.choices(["Online", "Store"], weights=[65, 35])[0]
        n_lines = rng.choices([1, 2, 3, 4], weights=[50, 30, 15, 5])[0]
        product_idx = rng.choices(range(n_products), weights=product_weights, k=n_lines)
        for line, p in enumerate(product_idx, start=1):
            _, category, price = PRODUCTS[p]
            max_qty = 10 if category == "Office Supplies" else 4
            local_price = price * GENERATION_FX[currency]
            rows.append({
                "order_id": f"SO-{100000 + n}",
                "line_number": line,
                "order_date": order_date.isoformat(),
                "customer_id": customer["customer_id"],
                "product_id": f"P{p + 1:03d}",
                "quantity": rng.randint(1, max_qty),
                "unit_price": f"{local_price:.0f}" if currency == "JPY" else f"{local_price:.2f}",
                "discount_pct": rng.choice(["0", "0", "0", "0", "0.05", "0.10", "0.15", "0.20"]),
                "currency": currency,
                "channel": channel,
            })

    # --- deliberate data problems (each touches a small random slice) ---
    def pick(share: float) -> list[int]:
        return rng.sample(range(len(rows)), max(1, int(len(rows) * share)))

    for i in pick(0.010):
        rows[i]["customer_id"] = ""                                       # missing customer
    for i in pick(0.005):
        rows[i]["quantity"] = rng.choice([0, -1, -2])                     # impossible quantity
    for i in pick(0.004):
        rows[i]["order_date"] = rng.choice(["2024-02-30", "31/12/2024", "not available", ""])
    for i in pick(0.004):
        rows[i]["product_id"] = "P999"                                    # product that doesn't exist
    for i in pick(0.010):
        if rows[i]["currency"] in ("USD", "EUR"):
            rows[i]["currency"] = f" {rows[i]['currency'].lower()} "      # fixable formatting
    for i in pick(0.003):
        rows[i]["currency"] = "XYZ"                                       # unknown currency
    for i in pick(0.003):
        rows[i]["discount_pct"] = "1.5"                                   # 150% discount?!
    for i in pick(0.012):
        rows.insert(rng.randint(0, len(rows)), dict(rows[i]))             # exported twice
    return rows


def generate(out_dir: Path = DEFAULT_OUT_DIR) -> None:
    rng = random.Random(SEED)
    products = make_products(rng)
    customers = make_customers(rng)
    orders = make_orders(rng, customers, n_products=len(PRODUCTS))

    write_csv(out_dir / "products.csv", products)
    write_csv(out_dir / "customers.csv", customers)
    write_csv(out_dir / "orders.csv", orders)

    fallback = {
        "amount": 1.0,
        "base": "USD",
        "date": END_DATE.isoformat(),
        "rates": {k: v for k, v in GENERATION_FX.items() if k != "USD"},
    }
    (out_dir / "fx_rates_fallback.json").write_text(json.dumps(fallback, indent=2), encoding="utf-8")

    print(f"Wrote {len(products)} products, {len(customers)} customers and "
          f"{len(orders)} order lines to {out_dir}")


if __name__ == "__main__":
    generate(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT_DIR)
