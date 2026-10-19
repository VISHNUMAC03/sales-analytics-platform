"""
Step 6 - DASHBOARD (Streamlit).

Streamlit turns a Python script into a web app. Every time you click a filter,
Streamlit re-runs this script from top to bottom with the new values.

Run it with:
    streamlit run dashboard/app.py
then open http://localhost:8501
"""

import sys
from datetime import date
from pathlib import Path

import duckdb
import pandas as pd
import plotly.express as px
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))  # lets us import pipeline.config
from pipeline.config import WAREHOUSE_PATH  # noqa: E402

BLUE = "#2a78d6"   # one colour for single-series charts; the title says what it is
GRID = "rgba(137, 135, 129, 0.25)"

st.set_page_config(page_title="Sales Analytics", page_icon="📊", layout="wide")


# ---------------------------------------------------------------------------
# Data access
# ---------------------------------------------------------------------------
@st.cache_data(ttl=300)  # remember results for 5 minutes so the app stays fast
def query(sql: str, params: list | None = None) -> pd.DataFrame:
    # read_only=True: the dashboard can never change the warehouse.
    with duckdb.connect(str(WAREHOUSE_PATH), read_only=True) as con:
        return con.execute(sql, params or []).df()


def style(fig, height: int = 340):
    """Shared, quiet chart styling: thin grid, no axis titles, compact margins."""
    fig.update_layout(height=height, margin=dict(l=8, r=8, t=8, b=8),
                      xaxis_title=None, yaxis_title=None, showlegend=False,
                      hoverlabel=dict(font_size=13))
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(gridcolor=GRID, zeroline=False)
    return fig


def money(value: float) -> str:
    """$248 / $78.3K / $1.25M - short enough to fit in a KPI tile."""
    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:,.2f}M"
    if abs(value) >= 10_000:
        return f"${value / 1_000:,.1f}K"
    return f"${value:,.0f}"


def hbar(df: pd.DataFrame, value: str, label: str, is_money: bool = True, height: int = 340):
    """Horizontal bar chart, biggest bar on top, value printed at the end of each bar."""
    fmt = "$%{x:,.0f}" if is_money else "%{x:,}"
    fig = px.bar(df, x=value, y=label, orientation="h", color_discrete_sequence=[BLUE])
    fig.update_traces(text=df[value], texttemplate=fmt, textposition="outside",
                      cliponaxis=False, hovertemplate=f"%{{y}}<br>{fmt}<extra></extra>")
    # Leave room on the right so the value labels are never cut off.
    fig.update_xaxes(range=[0, df[value].max() * 1.22], gridcolor=GRID, showgrid=True,
                     tickprefix="$" if is_money else "", tickformat="~s")
    fig.update_yaxes(showgrid=False)
    fig.update_layout(bargap=0.35)
    return style(fig, height)


def table(df: pd.DataFrame, money_cols: list[str]) -> None:
    """Show a table with $1,234 formatting while keeping the numbers sortable."""
    st.dataframe(df.style.format({c: "${:,.0f}" for c in money_cols}),
                 hide_index=True, use_container_width=True)


if not WAREHOUSE_PATH.exists():
    st.error("No warehouse found. Run the pipeline first:  `python -m pipeline.run_pipeline`")
    st.stop()

# ---------------------------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------------------------
bounds = query("SELECT MIN(order_date) AS lo, MAX(order_date) AS hi FROM reporting.sales_enriched")
min_date, max_date = bounds["lo"][0].date(), bounds["hi"][0].date()
regions = query("SELECT DISTINCT region FROM reporting.sales_enriched ORDER BY 1")["region"].tolist()
segments = query("SELECT DISTINCT segment FROM reporting.sales_enriched ORDER BY 1")["segment"].tolist()

st.sidebar.header("Filters")
picked = st.sidebar.date_input("Order date", value=(min_date, max_date),
                               min_value=min_date, max_value=max_date)
start, end = (picked if isinstance(picked, (list, tuple)) and len(picked) == 2
              else (min_date, max_date))
chosen_regions = st.sidebar.multiselect("Region", regions, placeholder="All regions")
chosen_segments = st.sidebar.multiselect("Segment", segments, placeholder="All segments")

# Empty selection means "everything". Values go in as ? parameters, never pasted into SQL.
WHERE = "order_date BETWEEN ? AND ? AND list_contains(?, region) AND list_contains(?, segment)"
PARAMS = [start, end, chosen_regions or regions, chosen_segments or segments]


def filtered(select: str, tail: str = "") -> pd.DataFrame:
    return query(f"SELECT {select} FROM reporting.sales_enriched WHERE {WHERE} {tail}", PARAMS)


# ---------------------------------------------------------------------------
# Header + KPI tiles
# ---------------------------------------------------------------------------
st.title("Sales Analytics")
st.caption(f"{start:%d %b %Y} to {end:%d %b %Y} · all amounts in US dollars")

kpi = filtered("""SUM(net_revenue_usd) AS revenue, SUM(profit_usd) AS profit,
                  COUNT(DISTINCT order_id) AS orders, COUNT(DISTINCT customer_id) AS customers""")
revenue, profit = kpi["revenue"][0] or 0, kpi["profit"][0] or 0
orders, customers = int(kpi["orders"][0]), int(kpi["customers"][0])

if orders == 0:
    st.warning("No sales match these filters.")
    st.stop()

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Revenue", money(revenue))
c2.metric("Profit", money(profit))
c3.metric("Profit margin", f"{profit / revenue:.1%}")
c4.metric("Orders", f"{orders:,}")
c5.metric("Customers", f"{customers:,}")
c6.metric("Avg order value", money(revenue / orders))

tab_sales, tab_customers, tab_quality = st.tabs(["Revenue & trends", "Customers", "Data quality"])

# ---------------------------------------------------------------------------
# Tab 1: revenue and trends
# ---------------------------------------------------------------------------
with tab_sales:
    st.subheader("Monthly revenue")
    monthly = filtered("date_trunc('month', order_date) AS month, SUM(net_revenue_usd) AS revenue",
                       "GROUP BY 1 ORDER BY 1")
    fig = px.line(monthly, x="month", y="revenue", markers=True,
                  color_discrete_sequence=[BLUE])
    fig.update_traces(line_width=2, marker_size=8,
                      hovertemplate="%{x|%b %Y}<br>$%{y:,.0f}<extra></extra>")
    fig.update_yaxes(tickprefix="$", tickformat="~s", rangemode="tozero")
    st.plotly_chart(style(fig), use_container_width=True)

    left, right = st.columns(2)
    with left:
        st.subheader("Revenue by category")
        cat = filtered("category, SUM(net_revenue_usd) AS revenue", "GROUP BY 1 ORDER BY 2")
        st.plotly_chart(hbar(cat, "revenue", "category"), use_container_width=True)
    with right:
        st.subheader("Revenue by region")
        reg = filtered("region, SUM(net_revenue_usd) AS revenue", "GROUP BY 1 ORDER BY 2")
        st.plotly_chart(hbar(reg, "revenue", "region"), use_container_width=True)

    st.subheader("Top 10 products")
    top_products = filtered("""product_name AS "Product", category AS "Category",
                               CAST(SUM(quantity) AS INTEGER) AS "Units",
                               SUM(net_revenue_usd) AS "Revenue",
                               SUM(profit_usd) AS "Profit" """,
                            "GROUP BY 1, 2 ORDER BY 4 DESC LIMIT 10")
    table(top_products, ["Revenue", "Profit"])

# ---------------------------------------------------------------------------
# Tab 2: customer performance
# ---------------------------------------------------------------------------
with tab_customers:
    left, right = st.columns([3, 2])
    with left:
        st.subheader("Top 10 customers")
        top_customers = filtered(
            """customer_name AS "Customer", segment AS "Segment", country AS "Country",
               COUNT(DISTINCT order_id) AS "Orders", SUM(net_revenue_usd) AS "Revenue",
               MAX(order_date) AS "Last order" """,
            "GROUP BY 1, 2, 3 ORDER BY 5 DESC LIMIT 10")
        table(top_customers, ["Revenue"])
    with right:
        st.subheader("Revenue by segment")
        seg = filtered("segment, SUM(net_revenue_usd) AS revenue", "GROUP BY 1 ORDER BY 2")
        st.plotly_chart(hbar(seg, "revenue", "segment", height=300), use_container_width=True)

    st.subheader("Customer tiers (lifetime, all dates)")
    st.caption("Customers ranked by lifetime revenue and split into four equal groups.")
    tiers = query("""
        SELECT customer_tier AS "Tier", COUNT(*) AS "Customers",
               SUM(revenue_usd) AS "Revenue", AVG(avg_order_value_usd) AS "Avg order value",
               SUM(revenue_usd) / (SELECT SUM(revenue_usd)
                                   FROM reporting.rpt_customer_performance) AS "Share of revenue"
        FROM reporting.rpt_customer_performance
        GROUP BY 1
        ORDER BY 3 DESC
    """)
    st.dataframe(tiers.style.format({"Revenue": "${:,.0f}", "Avg order value": "${:,.0f}",
                                     "Share of revenue": "{:.1%}"}),
                 hide_index=True, use_container_width=True)

# ---------------------------------------------------------------------------
# Tab 3: data quality - proof the pipeline is trustworthy
# ---------------------------------------------------------------------------
with tab_quality:
    last_run = query("SELECT * FROM meta.pipeline_runs ORDER BY started_at DESC LIMIT 1")
    if not last_run.empty:
        run = last_run.iloc[0]
        ok = run["status"] == "success"
        (st.success if ok else st.error)(
            f"{'✅' if ok else '❌'} Last pipeline run **{run['run_id']}** "
            f"finished with status **{run['status']}** at {run['finished_at']:%Y-%m-%d %H:%M}")

        left, right = st.columns(2)
        with left:
            st.subheader("Validation (Python)")
            st.dataframe(query("""SELECT entity AS "Dataset", input_rows AS "Rows in",
                                         clean_rows AS "Clean", rejected_rows AS "Rejected"
                                  FROM meta.validation_summary WHERE run_id = ?""",
                               [run["run_id"]]),
                         hide_index=True, use_container_width=True)
        with right:
            st.subheader("Quality checks (SQL)")
            checks = query("""SELECT check_name AS "Check", status AS "Status",
                                     failing_rows AS "Failing rows"
                              FROM meta.quality_results WHERE run_id = ? ORDER BY 1""",
                           [run["run_id"]])
            checks["Status"] = checks["Status"].map({"pass": "✅ pass", "fail": "❌ fail"})
            st.dataframe(checks, hide_index=True, use_container_width=True)

    st.subheader("Why rows were rejected")
    reasons = query("""SELECT entity || ': ' || rejection_reason AS reason, COUNT(*) AS rows
                       FROM raw.rejected_records GROUP BY 1 ORDER BY 2""")
    st.plotly_chart(hbar(reasons, "rows", "reason", is_money=False,
                         height=max(260, 30 * len(reasons))),
                    use_container_width=True)

    with st.expander("See the rejected rows"):
        st.dataframe(query("SELECT entity, rejection_reason, record FROM raw.rejected_records"),
                     hide_index=True, use_container_width=True)

    st.subheader("Recent pipeline runs")
    st.dataframe(query("""SELECT run_id, status, started_at, finished_at, fact_rows, error_message
                          FROM meta.pipeline_runs ORDER BY started_at DESC LIMIT 10"""),
                 hide_index=True, use_container_width=True)

st.caption(f"Data refreshed by the pipeline · dashboard generated {date.today():%d %b %Y}")
