# Beginner's Guide: Building a Sales Analytics Data Platform from Scratch

This guide assumes you have never built a data pipeline before. It explains **what** each
piece does, **why** it exists, and **how** to run it. Read it top to bottom once, then use
it as a reference while you rebuild or extend the project yourself.

**Contents**

0. [The big picture](#0-the-big-picture)
1. [Install your tools](#1-install-your-tools)
2. [Set up the project folder](#2-set-up-the-project-folder)
3. [Create the sample data](#3-create-the-sample-data)
4. [Step 1: Ingest](#4-step-1-ingest)
5. [Step 2: Clean and validate with Python](#5-step-2-clean-and-validate-with-python)
6. [Step 3: Load the warehouse](#6-step-3-load-the-warehouse)
7. [Step 4: Transform with SQL (the star schema)](#7-step-4-transform-with-sql-the-star-schema)
8. [Step 5: Data quality checks](#8-step-5-data-quality-checks)
9. [The orchestrator and logging](#9-the-orchestrator-and-logging)
10. [The dashboard](#10-the-dashboard)
11. [Automated tests](#11-automated-tests)
12. [Docker](#12-docker)
13. [Git and GitHub](#13-git-and-github)
14. [Explaining this project in an interview](#14-explaining-this-project-in-an-interview)
15. [Ideas to extend it](#15-ideas-to-extend-it)
16. [Glossary](#16-glossary)

---

## 0. The big picture

A company sells products in several countries. Sales data arrives as messy CSV exports, and
prices are in 7 different currencies. Managers want one trustworthy dashboard showing revenue,
trends and their best customers in US dollars.

A **data pipeline** is the automated assembly line that turns that messy input into
trustworthy numbers:

```
 SOURCES             INGEST           CLEAN            WAREHOUSE (SQL)                    DASHBOARD
 orders.csv    -->               -->  validate   -->  raw -> staging -> marts -> reporting -->  Streamlit
 customers.csv      copy to raw       reject bad                       |
 products.csv       storage           rows                        quality checks
 currency API
```

The architecture diagram you started from uses paid cloud tools. This project uses free tools
that do the same jobs, so everything runs on your laptop:

| Job | In the diagram (cloud, paid) | In this project (free, local) |
|---|---|---|
| Pull data from sources | Fivetran, Segment, Airbyte | `pipeline/ingest.py` |
| Store raw files | Amazon S3 | `data/raw/` folder, optional S3 upload |
| Data warehouse | Snowflake | DuckDB, a database stored in one file |
| SQL transformations | dbt | `.sql` files in `sql/`, run by `pipeline/transform.py` |
| Data quality monitoring | Monte Carlo | SQL tests in `sql/tests/` |
| Dashboards | Hex, Looker | Streamlit app in `dashboard/` |

Because the *concepts* are identical, you can honestly say in an interview: "I built the same
architecture with open-source tools, and here is how it maps to Snowflake and dbt."

---

## 1. Install your tools

You need four things. Install them once.

| Tool | What it is | Get it from |
|---|---|---|
| **Python 3.10+** | The programming language for the pipeline | python.org/downloads. On Windows, tick **"Add python.exe to PATH"** during install. |
| **Git** | Tracks every change to your code | git-scm.com. Default options are fine. |
| **VS Code** | A code editor | code.visualstudio.com. Then install the "Python" extension. |
| **Docker Desktop** | Runs your project in a container | docker.com/products/docker-desktop |

You also need a free **GitHub account** at github.com.

Check everything is installed. Open **PowerShell** (press Start, type "PowerShell") and run:

```powershell
python --version
git --version
docker --version
```

Each command should print a version number. If one says "not recognized", that tool isn't
installed or isn't on your PATH. Close and reopen PowerShell after installing.

---

## 2. Set up the project folder

```powershell
cd $HOME
mkdir sales-analytics-platform
cd sales-analytics-platform
```

### Virtual environment

A **virtual environment** ("venv") is a private box of Python libraries for this one project,
so it can't clash with other projects on your computer.

```powershell
python -m venv .venv                 # create the box (a folder called .venv)
.venv\Scripts\activate               # step into it. Your prompt now starts with (.venv)
```

> If PowerShell says running scripts is disabled, run this once and try again:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

You must **activate the venv every time** you open a new terminal to work on the project.

### Install the libraries

`requirements.txt` lists every library with an exact version ("pinning"), so the project
behaves the same on every machine:

```powershell
pip install -r requirements.txt
```

### Folder layout

```
sales-analytics-platform/
├── data/source/      input files (committed to Git so anyone can run the project)
├── pipeline/         Python code for each pipeline step
├── sql/              SQL models and quality tests
├── dashboard/        the Streamlit app
├── tests/            automated tests
├── scripts/          helper scripts (data generator)
├── docs/             this guide
├── requirements.txt, Dockerfile, docker-compose.yml, README.md, .gitignore
```

Separating code by responsibility makes it easy to find things and easy to test each part
on its own.

### `pipeline/config.py`: one place for settings

Every other file imports its paths from here. If you want to move the warehouse, you change
one line, or set a value in a `.env` file. `.env.example` shows the options. Copy it to `.env`
if you need to change anything. `.env` is never committed to Git, because that's where secrets
like AWS keys would go.

---

## 3. Create the sample data

```powershell
python scripts/generate_sample_data.py
```

This writes four files into `data/source/`:

| File | Rows | Contents |
|---|---|---|
| `products.csv` | ~33 | 30 products in 5 categories, with price and cost |
| `customers.csv` | ~304 | Customers in 9 countries, 3 regions, 3 segments |
| `orders.csv` | ~5,600 | Order lines from 2024 and 2025, priced in local currency |
| `fx_rates_fallback.json` | | Backup exchange rates in case the internet is down |

**Why fake data?** It's free and needs no account. It also uses a fixed random seed, so it's
identical on every computer. Most importantly, it **deliberately contains mistakes** that real
exports have:

- Rows exported twice (duplicates)
- Missing customer IDs
- Impossible dates like `2024-02-30` or `not available`
- Quantities of `0` or `-2`
- A product ID `P999` that doesn't exist
- A currency `XYZ` that doesn't exist
- A 150% discount
- Fixable formatting such as `" usd "` and `"  germany "`
- Invalid emails such as `ann at example.com`

Open `orders.csv` in VS Code or Excel and look at it. Get a feel for your raw data before
writing any code; real data engineers always do this first.

The generator also builds in realistic patterns: sales grow over time, peak in
November and December, and a few customers buy far more than the rest.

> Want a real public dataset instead? Kaggle's "Superstore Sales" is a popular choice. You'd
> rename its columns to match ours in the cleaning step.

---

## 4. Step 1: Ingest

**File:** `pipeline/ingest.py` and `pipeline/storage.py`

**Ingestion** means collecting data from where it lives and bringing it into your platform.
We have two kinds of source, like most companies:

1. **Files** (CSV exports from the sales system)
2. **An API.** We call the free [Frankfurter](https://www.frankfurter.app/) API to get today's
   exchange rates, because orders arrive in 7 currencies.

### The raw zone

Before touching any data, we save an **exact, untouched copy** of everything:

```
data/raw/orders/20261019T112027Z/orders.csv
data/raw/fx_rates/20261019T112027Z/fx_rates.json
         ^source  ^run_id (date and time of the run, in UTC)
```

Why keep untouched copies? If a bug in the cleaning code damages data, you can re-process
from the originals. You can also answer "what exactly did we receive on Tuesday?" In
production this would be an Amazon S3 bucket. Set `S3_BUCKET` in `.env` and `storage.py`
uploads every file there too.

### Calling an API safely

Look at `fetch_fx_rates`. Three habits worth copying:

- **Timeout.** `requests.get(..., timeout=10)` means a slow server can't freeze the pipeline forever.
- **Retries.** Networks fail randomly, so we try up to 3 times and wait a bit longer each time.
- **Fallback.** If the API is still down, we log a warning and use `fx_rates_fallback.json`.
  The pipeline keeps working, and the log tells you it happened.

Try it in Python:

```powershell
python -c "import requests; print(requests.get('https://api.frankfurter.app/latest?from=USD&to=EUR,GBP').json())"
```

---

## 5. Step 2: Clean and validate with Python

**File:** `pipeline/validate.py`

This is the most important step for trust. Every row goes into one of two buckets:

- **Clean** rows go to the warehouse.
- **Rejected** rows go to `data/rejected/`, each with a reason a human can read.

Never silently delete bad data. Someone will ask "why don't the numbers match the source
system?", and the rejected files answer that.

### Fixable vs. unfixable

| Problem | Decision | Why |
|---|---|---|
| `" usd "` | Fix to `USD`, keep the row | The meaning is obvious |
| `"  germany "` | Fix to `Germany` | Same |
| `ann at example.com` | Blank the email, keep the customer | The customer is still real |
| Missing customer ID | Reject | We can't guess who bought it |
| Quantity `-2` | Reject | We can't guess the real quantity |
| Date `2024-02-30` | Reject | We can't guess the real date |

### How the code works

1. **`check_columns`.** If the source suddenly renames a column, fail immediately with a clear
   message instead of producing wrong numbers later. This is called *failing fast*.
2. **`standardize_text`.** Trim spaces and turn empty strings into proper missing values.
3. **`remove_duplicates`.** First drop exact duplicate rows. Then drop rows that repeat the
   *business key*: two rows for "order SO-100001, line 1" can't both be right.
4. **Convert types.** We read every column as text (`dtype=str`) so pandas doesn't guess.
   Then `pd.to_numeric(..., errors="coerce")` and `pd.to_datetime(..., errors="coerce")`
   convert what they can and turn everything else into "missing", which the rules then catch.
5. **`split_by_rules`.** A list of `(reason, mask_of_bad_rows)` pairs. Each row is rejected
   with the **first** rule it breaks.
6. **Referential checks.** An order must point to a customer and a product that exist. So we
   clean products and customers first, then pass their IDs into `clean_orders`.

A **mask** is a column of True/False values, one per row. `df["quantity"] <= 0` gives True
for every row with a bad quantity. Masks are how pandas filters rows without loops.

After a run, open `data/rejected/orders_rejected.csv`. Every bad row is there, with a
`rejection_reason` column.

---

## 6. Step 3: Load the warehouse

**File:** `pipeline/warehouse.py`

A **data warehouse** is a database designed for analysis: summing millions of rows quickly,
rather than updating one row at a time like an app database.

We use **DuckDB**. It's free, needs no server, and stores everything in one file,
`warehouse/sales.duckdb`. It speaks standard SQL, so your skills transfer directly to
Snowflake, BigQuery or Redshift.

The warehouse is organised into **schemas**, which are like folders for tables:

| Schema | Contains | Built by |
|---|---|---|
| `raw` | Clean CSVs loaded as-is, plus all rejected records | `warehouse.py` |
| `staging` | Correct data types and clear column names | `sql/staging/` |
| `marts` | The star schema: facts and dimensions | `sql/marts/` |
| `reporting` | Ready-to-chart tables for the dashboard | `sql/reporting/` |
| `meta` | Pipeline runs, validation counts, test results | `warehouse.py` |

We use `CREATE OR REPLACE TABLE`, a **full refresh**. Running the load twice gives the same
result as running it once. That property is called **idempotent**, and it makes re-running after
a failure safe.

### Explore the warehouse yourself

```powershell
python
```
```python
import duckdb
con = duckdb.connect("warehouse/sales.duckdb", read_only=True)
con.sql("SHOW ALL TABLES").show()
con.sql("SELECT * FROM marts.fct_sales LIMIT 5").show()
con.sql("SELECT rejection_reason, COUNT(*) FROM raw.rejected_records GROUP BY 1").show()
```

Type `exit()` to leave Python.

---

## 7. Step 4: Transform with SQL (the star schema)

**Files:** `sql/staging/`, `sql/marts/`, `sql/reporting/`, run by `pipeline/transform.py`

**One SQL file builds one table.** `transform.py` runs the layers in order: staging, then
marts, then reporting. Inside a layer, files run alphabetically. When a table needs another
table from the same layer, a number prefix sets the order. For example,
`01_sales_enriched.sql` runs before `02_rpt_monthly_revenue.sql`. This is exactly how
**dbt** works, so moving to dbt later is mostly copying files.

### Layer 1: staging

Only renaming and type casting (`CAST(order_date AS DATE)`). No joins, no business logic.
Keeping each layer to one job makes bugs easy to find.

### Layer 2: marts, the star schema

This is **dimensional modelling**, the most important concept in analytics engineering.

- A **fact table** records *events* and their *numbers*. Our `fct_sales` has **one row per
  order line**. That's its **grain**: always be able to say what one row means. It holds the
  measures (quantity, revenue, cost, profit) and **keys** that point to dimensions.
- **Dimension tables** describe the *who, what and when*:
  - `dim_customers` covers who bought: country, region, segment.
  - `dim_products` covers what was bought: category, price band.
  - `dim_date` covers when: year, quarter, month, weekday.

Draw it and the fact sits in the middle with dimensions around it, like a star:

```
                dim_customers
                      |
   dim_date ---- fct_sales ---- dim_products
```

Why bother? Every business question becomes "join the fact to the dimensions you need, then
group by". "Revenue by region and quarter" joins `fct_sales` to `dim_customers` and `dim_date`.

### Key ideas inside `fct_sales.sql`

- **Currency conversion.** `rate_per_usd` is how many euros (or yen…) 1 dollar buys, so
  `amount_local / rate_per_usd = amount_usd`.
- **`LEFT JOIN` on purpose.** If a currency had no rate, an `INNER JOIN` would silently
  drop that sale and under-report revenue. A `LEFT JOIN` keeps the row with a `NULL` amount,
  which a quality check then catches. Silent data loss is the worst kind of bug.
- **CTE.** `WITH priced AS (...)` names an intermediate result so the final `SELECT` stays
  readable.

### Layer 3: reporting

- `01_sales_enriched` joins the star back into one wide table. Dashboards love this.
- `02_rpt_monthly_revenue` computes monthly KPIs. `LAG()` is a **window function**: it
  looks at the previous month's row to calculate growth.
- `03_rpt_customer_performance` holds lifetime value per customer. `NTILE(4)` splits customers
  into 4 equal groups (Platinum, Gold, Silver, Bronze), and `RANK()` ranks them.

Window functions come up constantly in data interviews. Practise these three.

---

## 8. Step 5: Data quality checks

**Files:** `sql/tests/*.sql`, run by `pipeline/quality.py`

Python validation checked **individual input rows**. These checks look at the **finished
tables as a whole**.

The convention, borrowed from dbt, is that **each test is a query that returns the bad rows**.
Zero rows means pass. Any rows means fail, and the pipeline stops with an error.

| Test | Question it answers |
|---|---|
| `fct_sales_unique_line` | Does each order line appear exactly once? |
| `fct_sales_required_fields` | Are keys and money columns ever empty? |
| `fct_sales_valid_amounts` | Positive quantity, sensible discount, net ≤ gross? |
| `fct_sales_customer_exists` | Does every sale point to a real customer? |
| `fct_sales_product_exists` | Does every sale point to a real product? |
| `fct_sales_no_future_dates` | Any orders dated in the future? |
| `dim_customers_unique` | One row per customer? A duplicate would double-count revenue in joins. |
| `dim_products_unique` | One row per product? |
| `reporting_revenue_reconciles` | Do the reporting tables add up to the fact table? |

Results are saved in `meta.quality_results` and shown on the dashboard's **Data quality** tab.

**Try breaking it on purpose.** It's the best way to learn. In `sql/marts/dim_customers.sql`,
add `UNION ALL (SELECT * FROM staging.stg_customers LIMIT 1)` before the final `;` and run
the pipeline. This sneaks in one duplicate customer. `dim_customers_unique` fails. So does
`reporting_revenue_reconciles`, because the duplicate makes that customer's sales count
twice in the joined reporting table. The run is marked failed, the program exits with code 1,
and the log explains why. Then undo your change.

---

## 9. The orchestrator and logging

**Files:** `pipeline/run_pipeline.py`, `pipeline/logger.py`

The orchestrator runs every step in order:

```powershell
python -m pipeline.run_pipeline            # normal run
python -m pipeline.run_pipeline --offline  # without internet (fallback exchange rates)
```

`-m pipeline.run_pipeline` means "run the module `run_pipeline` inside the package
`pipeline`". It's run from the project folder so Python can find the package.

### Logging, not print

`print()` vanishes when a job runs unattended in Docker or at 3am on a schedule. A logger
writes timestamped, levelled lines to the screen **and** to `logs/pipeline.log`:

```
2026-10-19 13:20:28 | INFO     | pipeline.validate | Validated orders: 5631 in -> 5410 clean, 221 rejected
2026-10-19 13:20:28 | WARNING  | pipeline.validate | customers: blanked 5 invalid email address(es)
2026-10-19 13:20:28 | ERROR    | pipeline.quality  | FAIL  dim_customers_unique (1 failing rows)
```

### Handling failures

- The whole run is wrapped in `try / except`.
- On failure, `logger.exception` writes the **full traceback** to the log file.
- The failed run is recorded in `meta.pipeline_runs` with its error message.
- The program exits with **code 1**. Docker, schedulers and GitHub Actions all read the exit
  code to decide whether a job worked. Code 0 means success.

---

## 10. The dashboard

**File:** `dashboard/app.py`

```powershell
streamlit run dashboard/app.py
```

Your browser opens http://localhost:8501. Press `Ctrl+C` in the terminal to stop it.

**Streamlit** turns a Python script into a web app. Every click on a filter re-runs the
script from top to bottom with the new values.

What it shows:

- **KPI tiles** for revenue, profit, margin, orders, customers and average order value.
- **Revenue & trends** with monthly revenue (note the November and December peaks), revenue by
  category and region, and the top products.
- **Customers** with top customers, revenue by segment, and lifetime customer tiers.
- **Data quality** with the last run's status, validation counts, quality-check results, why rows
  were rejected, and run history. This tab shows a reviewer you think about **trust**, not
  just charts.

Good practices in the code:

- **`read_only=True`** means the dashboard can never change the warehouse.
- **`?` parameters.** Filter values are passed separately from the SQL, never pasted into it.
  This prevents **SQL injection**.
- **`@st.cache_data`** remembers query results for 5 minutes, so the app stays fast.

---

## 11. Automated tests

**Folder:** `tests/`

```powershell
pytest            # or: pytest -v   for one line per test
```

| File | Kind of test | What it checks |
|---|---|---|
| `test_validate.py` | **Unit tests** | Each cleaning rule on tiny hand-made tables. Fast and precise. |
| `test_pipeline.py` | **End-to-end test** | Generates data in a temporary folder, runs the whole pipeline offline, and checks the warehouse. |
| `test_dashboard.py` | **Smoke test** | Runs the dashboard without a browser and checks it doesn't crash. |

Tests are your safety net. Change a rule, run `pytest`, and you know within seconds whether you
broke something. `@pytest.mark.parametrize` runs the same test with several inputs, like four
different bad dates.

---

## 12. Docker

**Files:** `Dockerfile`, `docker-compose.yml`, `.dockerignore`

"It works on my machine" is a classic problem. **Docker** packages your code together with the
exact Python version and libraries into an **image**. A running image is a **container**. It
behaves identically on any computer with Docker.

### The Dockerfile

This is the recipe for the image. Each line is commented in the file. In short: start from
official Python 3.11, install `requirements.txt`, copy the code, and set the default command
to run the pipeline.

Requirements are copied and installed **before** the code. Docker caches each step, so when you
change only code, the slow install step is reused.

### docker-compose.yml

This file describes two **services** that share the same image:

1. `pipeline` runs once and exits.
2. `dashboard` starts **only if the pipeline succeeded** (`service_completed_successfully`)
   and serves on port 8501.

**Volumes** (`./warehouse:/app/warehouse`) share folders between your computer and the
containers. The warehouse the pipeline writes is visible to the dashboard and to you.

### Run it

Start Docker Desktop first and wait until it says "Engine running".

```powershell
docker compose up --build      # build, run pipeline, then start the dashboard
```

Open http://localhost:8501. Press `Ctrl+C` to stop it, then run `docker compose down` to clean up.

Other useful commands:

```powershell
docker compose run --rm pipeline   # just run the pipeline once
docker compose logs pipeline       # see the pipeline output
docker images                      # list images on your computer
```

---

## 13. Git and GitHub

**Git** records snapshots ("commits") of your project on your computer. **GitHub** is a
website that hosts a copy of your Git project, which is your public portfolio.

### 13.1 Tell Git who you are (once per computer)

```powershell
git config --global user.name  "Your Name"
git config --global user.email "you@example.com"   # use the email of your GitHub account
```

### 13.2 What NOT to upload

`.gitignore` lists files Git must ignore:

- `.venv/`, because anyone can recreate it with `pip install`.
- `.env`, because it holds secrets. **Never commit passwords or keys.** Bots scan GitHub for them
  within minutes.
- `data/raw/`, `data/clean/`, `warehouse/` and `logs/`, because the pipeline recreates them.

`data/source/` **is** committed, so anyone who clones your repo can run the project immediately.

### 13.3 Make commits

```powershell
git init                       # start tracking this folder (once)
git status                     # what changed? Run this often
git add .                      # stage all changes for the next snapshot
git commit -m "Add ingestion step for CSV files and FX API"
git log --oneline              # list your snapshots
```

Good commit messages say **what** changed, in the imperative: "Add…", "Fix…", "Refactor…".
Commit after each working step. A history of small, clear commits looks professional.

### 13.4 Create the GitHub repository and push

**Option A: GitHub CLI (fastest)**

```powershell
gh auth login       # choose GitHub.com, HTTPS, "Login with a web browser", then follow the code
gh repo create sales-analytics-platform --public --source . --remote origin --push
```

**Option B: the website**

1. Go to github.com, click **+** (top right), then **New repository**.
2. Name it `sales-analytics-platform`, choose **Public**, and **don't** tick "Add a README"
   (you already have one). Click **Create repository**.
3. GitHub shows commands. Run these, replacing `YOUR-USERNAME`:

```powershell
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/sales-analytics-platform.git
git push -u origin main
```

A browser window asks you to sign in the first time.

### 13.5 After the first push

1. **Fix the badge.** In `README.md`, replace `YOUR-GITHUB-USERNAME` with your username, then run:
   ```powershell
   git add README.md
   git commit -m "Point CI badge at my repository"
   git push
   ```
2. **Watch CI run.** Open the **Actions** tab on your repo. `.github/workflows/ci.yml` makes
   GitHub run the tests, the full pipeline and the Docker build on a fresh machine for every push.
   A green tick proves the project works, not just on your laptop.
3. **Polish the repo page.** Click the gear next to **About** and add a description and
   topics: `data-engineering`, `etl`, `python`, `sql`, `duckdb`, `docker`, `streamlit`,
   `data-quality`.
4. **Pin it.** On your GitHub profile, click **Customize your pins** and select this repository.
5. **Add a license** (optional). Click **Add file**, then **Create new file**, name it
   `LICENSE`, pick "MIT" from the template picker, and commit.

### 13.6 The everyday loop from now on

```powershell
# edit code...
pytest                       # make sure nothing broke
git add .
git commit -m "Describe the change"
git push
```

---

## 14. Explaining this project in an interview

A 60-second version to practise out loud:

> "I built an automated sales analytics platform. It ingests order, customer and product CSVs
> plus live exchange rates from a REST API, with retries and a fallback. Every input is kept
> untouched in a raw zone, like S3. Python and pandas validate the data: schema checks,
> type conversion, de-duplication, business rules and referential integrity. Bad rows are kept
> with a reason instead of being silently dropped. Clean data is loaded into a DuckDB
> warehouse and transformed with layered SQL models into a star schema: one sales fact table
> at order-line grain, plus customer, product and date dimensions. Nine SQL data-quality tests
> run after every build and fail the pipeline if anything is off. Results feed a Streamlit
> dashboard covering revenue, trends, customer tiers and pipeline health. It's containerised with
> Docker Compose, and GitHub Actions runs the unit and end-to-end tests on every push."

Questions to be ready for:

- **"What's the grain of your fact table?"** One row per order line.
- **"Why LEFT JOIN in the fact?"** So missing lookups show up as NULLs that tests catch,
  instead of rows silently disappearing.
- **"How would you scale this?"** Swap DuckDB for Snowflake, move the SQL into dbt, schedule
  it with Airflow, store raw files in S3, and load incrementally instead of full refresh.
- **"What happens when the API is down?"** Three retries with back-off, then fallback rates
  and a warning in the log.
- **"How do you know the numbers are right?"** Row-level validation, model-level SQL tests,
  a reconciliation test, rejected-row audit trail, and automated tests in CI.

---

## 15. Ideas to extend it

Pick one at a time. Each makes a good commit and a good interview story.

1. **dbt.** Install `dbt-duckdb`, move `sql/` into a dbt project, and replace `sql/tests` with dbt tests.
2. **Incremental loads.** Process only new orders since the last successful run.
3. **Scheduling.** Add a `schedule:` (cron) trigger to the GitHub Actions workflow, or use Airflow.
4. **Real S3.** Create a bucket, set `S3_BUCKET` in `.env`, and watch raw files upload.
5. **Historical exchange rates.** Frankfurter supports date ranges, so convert each order at its own day's rate.
6. **Deploy the dashboard** for free on Streamlit Community Cloud.
7. **LLM feature.** Let a user type "Which region grew fastest last quarter?" and have an LLM
   draft a SQL query. Show it for review, then run it on a **read-only** connection with a row
   limit. Never let generated SQL write to the warehouse.

---

## 16. Glossary

| Term | Meaning |
|---|---|
| **API** | A web address a program calls to get data, usually as JSON |
| **CI (continuous integration)** | Automatically testing code on every push |
| **Container / image** | A packaged, runnable copy of an app and everything it needs |
| **CTE** | `WITH name AS (...)`: a named sub-query that makes SQL readable |
| **Dimension** | A table describing who, what or when (customers, products, dates) |
| **ETL / ELT** | Extract, Transform, Load: the general name for this kind of pipeline |
| **Fact** | A table of events with numeric measures (sales lines) |
| **Grain** | What one row of a table represents |
| **Idempotent** | Running it twice gives the same result as running it once |
| **Orchestrator** | The code that runs pipeline steps in order and handles failure |
| **Raw zone / data lake** | Storage for untouched copies of source data |
| **Referential integrity** | Every key points to a row that actually exists |
| **Schema** | A named group of tables inside a database |
| **Star schema** | One fact table surrounded by dimension tables |
| **venv** | A private set of Python libraries for one project |
| **Window function** | SQL that looks at other rows without grouping them away (`LAG`, `RANK`, `NTILE`) |
