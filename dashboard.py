"""
Contract Renewal Agent — Streamlit Dashboard
Run: streamlit run dashboard.py
"""
import sys
import os
import glob
import subprocess
import sqlite3
from datetime import date, timedelta

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# ── bootstrap path so config/agent imports work from any cwd ──────────────────
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
import config  # noqa: E402  (runs load_dotenv)

# ── constants ─────────────────────────────────────────────────────────────────
MEMOS_DIR = os.path.join(ROOT, "outputs", "memos")
URGENCY_ORDER = ["Critical", "High", "Medium", "Low"]
URGENCY_COLOR = {
    "Critical": "#d62728",
    "High":     "#e87722",
    "Medium":   "#e6b800",
    "Low":      "#2ca02c",
}
URGENCY_BG = {
    "Critical": "#fde8e8",
    "High":     "#fff0e0",
    "Medium":   "#fffde7",
    "Low":      "",
}

# ── page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Contract Renewal Agent",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── global CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* sidebar */
    [data-testid="stSidebar"] { background: #f2f2f2 !important; }
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] div  { color: #333333 !important; }
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3  { color: #1a1a1a !important; }
    /* urgency badges */
    .badge-critical { background:#d62728; color:#fff; padding:2px 8px;
                      border-radius:4px; font-size:12px; font-weight:600; }
    .badge-high     { background:#e87722; color:#fff; padding:2px 8px;
                      border-radius:4px; font-size:12px; font-weight:600; }
    .badge-medium   { background:#e6b800; color:#1a1a1a; padding:2px 8px;
                      border-radius:4px; font-size:12px; font-weight:600; }
    .badge-low      { background:#2ca02c; color:#fff; padding:2px 8px;
                      border-radius:4px; font-size:12px; }
    /* tight metric labels */
    [data-testid="stMetricLabel"] { font-size: 13px !important; }
    /* multiselect tags — override Streamlit's default red */
    [data-baseweb="tag"] {
        background-color: #444444 !important;
        border-color: #444444 !important;
    }
    [data-baseweb="tag"] span {
        color: #ffffff !important;
    }
    [data-baseweb="tag"] svg {
        fill: #ffffff !important;
    }
</style>
""", unsafe_allow_html=True)


# ── data helpers ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=30)
def load_contracts() -> pd.DataFrame:
    if not os.path.exists(config.DB_PATH):
        return pd.DataFrame()
    conn = sqlite3.connect(config.DB_PATH)
    try:
        df = pd.read_sql_query(
            "SELECT * FROM contracts ORDER BY expiry_date", conn
        )
    except Exception:
        return pd.DataFrame()
    finally:
        conn.close()

    if df.empty:
        return df

    today = date.today()
    df["days_left"] = pd.to_datetime(df["expiry_date"]).apply(
        lambda d: (d.date() - today).days
    )
    df["urgency"] = df["days_left"].apply(
        lambda d: "Critical" if d <= 30
        else "High"     if d <= 60
        else "Medium"   if d <= 90
        else "Low"
    )
    df["value_display"] = df.apply(
        lambda r: f"{r['currency']} {r['value']:,.0f}", axis=1
    )
    # normalise auto_renewal to readable string
    df["auto_renewal_label"] = df["auto_renewal"].apply(
        lambda v: "Yes" if v in (1, "1", "Yes", True) else "No"
    )
    return df


@st.cache_data(ttl=30)
def load_memos() -> dict:
    memos = {}
    for path in glob.glob(os.path.join(MEMOS_DIR, "*.md")):
        cid = os.path.basename(path).replace("_renewal_memo.md", "")
        with open(path) as f:
            memos[cid] = f.read()
    return memos


def _has_api_key() -> bool:
    return bool(config.ANTHROPIC_API_KEY and config.ANTHROPIC_API_KEY.startswith("sk-"))


# ── sidebar ───────────────────────────────────────────────────────────────────

df_all = load_contracts()

with st.sidebar:
    st.markdown("## 📋 Contract Renewal\nAgent Dashboard")
    st.markdown("---")

    if df_all.empty:
        st.warning("Database is empty. Seed data or run the agent first.")
        sel_cats = sel_urgency = sel_curr = []
    else:
        st.markdown("### Filters")
        all_cats = sorted(df_all["category"].dropna().unique())
        sel_cats = st.multiselect("Category", all_cats, default=list(all_cats))

        sel_urgency = st.multiselect(
            "Urgency", URGENCY_ORDER, default=URGENCY_ORDER
        )

        all_curr = sorted(df_all["currency"].dropna().unique())
        sel_curr = st.multiselect("Currency", all_curr, default=list(all_curr))

        st.markdown("---")
        st.markdown(
            f"**{len(df_all)}** contracts total  \n"
            f"**{len(df_all[df_all['urgency']=='Critical'])}** critical  •  "
            f"**{len(df_all[df_all['urgency'].isin(['Critical','High','Medium'])])}** flagged"
        )

    st.markdown("---")
    st.markdown("### Run Agent")

    if not _has_api_key():
        st.info("Set `ANTHROPIC_API_KEY` in `.env` to enable the full pipeline.")
        run_disabled = True
    else:
        st.success("API key configured")
        run_disabled = False

    run_btn = st.button(
        "▶  Run Agent Now",
        type="primary",
        disabled=run_disabled,
        use_container_width=True,
    )
    agent_placeholder = st.empty()

    st.markdown("---")
    st.caption(f"DB: `{config.DB_PATH}`")
    st.caption(f"Contracts dir: `{config.CONTRACTS_DIR}`")


# ── apply filters ─────────────────────────────────────────────────────────────

# Always filter from df_all so the result keeps all columns even when zero rows match.
# An empty sel_* list means "nothing passes" — isin([]) returns False for all rows.
if not df_all.empty:
    df = df_all[
        df_all["category"].isin(sel_cats) &
        df_all["urgency"].isin(sel_urgency) &
        df_all["currency"].isin(sel_curr)
    ].copy()
else:
    df = df_all.copy()


# ── main header ───────────────────────────────────────────────────────────────

st.markdown("# Contract Renewal Dashboard")
st.markdown(
    f"Procurement intelligence  ·  {date.today().strftime('%A, %B %d %Y')}"
)
st.divider()


# ── empty state ───────────────────────────────────────────────────────────────

if df_all.empty:
    st.info(
        "No contracts in the database yet.  \n"
        "Run `python synthetic_data/seed_database.py` to pre-seed records, "
        "or click **Run Agent Now** (requires API key) to ingest the PDFs."
    )
    st.stop()


# ── metrics row ───────────────────────────────────────────────────────────────

if df.empty:
    st.info("No contracts match the current filters. Adjust the sidebar filters to see results.")
    st.stop()

total       = len(df)
critical    = len(df[df["urgency"] == "Critical"])
high        = len(df[df["urgency"] == "High"])
medium      = len(df[df["urgency"] == "Medium"])
low         = len(df[df["urgency"] == "Low"])
memos_count = len(load_memos())

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Total contracts",   total)
c2.metric("Critical  ≤ 30 d", critical, delta=f"+{critical}" if critical else None,
          delta_color="inverse")
c3.metric("High  31 – 60 d",  high,     delta=f"+{high}" if high else None,
          delta_color="inverse")
c4.metric("Medium  61 – 90 d", medium)
c5.metric("Low  > 90 d",      low)
c6.metric("Memos generated",  memos_count)

# verify the buckets add up (sanity caption)
st.caption(f"{critical} critical + {high} high + {medium} medium + {low} low = {critical+high+medium+low} of {total} contracts")

st.divider()


# ── tabs ──────────────────────────────────────────────────────────────────────

tab_table, tab_timeline, tab_risk, tab_memos = st.tabs([
    "📄  Contracts Table",
    "📅  Expiry Timeline",
    "🗺  Risk Map",
    "📝  Memos",
])


# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — CONTRACTS TABLE
# ─────────────────────────────────────────────────────────────────────────────

with tab_table:
    if df.empty:
        st.info("No contracts match the current filters.")
    else:
        col_search, col_sort = st.columns([3, 1])
        with col_search:
            search = st.text_input("Search vendor or category", placeholder="e.g. Acme, IT Services")
        with col_sort:
            sort_col = st.selectbox(
                "Sort by", ["days_left", "value", "vendor", "expiry_date"],
                format_func=lambda x: {
                    "days_left": "Days Left",
                    "value": "Value",
                    "vendor": "Vendor",
                    "expiry_date": "Expiry Date",
                }[x]
            )

        df_view = df.copy()
        if search:
            mask = (
                df_view["vendor"].str.contains(search, case=False, na=False) |
                df_view["category"].str.contains(search, case=False, na=False)
            )
            df_view = df_view[mask]

        df_view = df_view.sort_values(sort_col)

        display = df_view[[
            "vendor", "category", "value_display", "expiry_date",
            "days_left", "urgency", "auto_renewal_label",
            "price_escalation", "sla_penalty",
        ]].rename(columns={
            "vendor":            "Vendor",
            "category":          "Category",
            "value_display":     "Value",
            "expiry_date":       "Expiry Date",
            "days_left":         "Days Left",
            "urgency":           "Urgency",
            "auto_renewal_label":"Auto-Renewal",
            "price_escalation":  "Price Escalation",
            "sla_penalty":       "SLA Penalty",
        })

        def _row_style(row):
            bg = URGENCY_BG.get(row["Urgency"], "")
            return [f"background-color: {bg}" if bg else "" for _ in row]

        st.dataframe(
            display.style.apply(_row_style, axis=1),
            use_container_width=True,
            height=500,
        )
        st.caption(f"Showing {len(display)} of {len(df_all)} contracts")


# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — EXPIRY TIMELINE
# ─────────────────────────────────────────────────────────────────────────────

with tab_timeline:
    max_days = st.slider(
        "Show contracts expiring within … days",
        min_value=30, max_value=730, value=365, step=30,
    )
    df_time = df[df["days_left"] <= max_days].copy()

    if df_time.empty:
        st.info(f"No contracts expiring within {max_days} days under current filters.")
    else:
        df_time = df_time.sort_values("days_left")
        df_time["start_dt"]  = pd.to_datetime(df_time["start_date"])
        df_time["expiry_dt"] = pd.to_datetime(df_time["expiry_date"])
        # Plotly timeline needs start < end; clip start to today if in the past
        today_ts = pd.Timestamp(date.today())
        df_time["bar_start"] = df_time["start_dt"].clip(lower=today_ts - pd.Timedelta(days=365))

        fig = px.timeline(
            df_time,
            x_start="bar_start",
            x_end="expiry_dt",
            y="vendor",
            color="urgency",
            color_discrete_map=URGENCY_COLOR,
            hover_data={
                "category":     True,
                "value_display":True,
                "days_left":    True,
                "bar_start":    False,
                "expiry_dt":    False,
            },
            labels={"vendor": "", "urgency": "Urgency"},
            title=f"Contracts expiring within {max_days} days ({len(df_time)} shown)",
        )
        fig.update_yaxes(autorange="reversed", tickfont=dict(size=11))

        # Plotly timeline axes use millisecond Unix timestamps internally;
        # passing ISO strings to add_vline/add_vrect triggers a type error in
        # Plotly's annotation mean-position calculation.
        def _ts_ms(d) -> int:
            return int(pd.Timestamp(d).timestamp() * 1000)

        today_ms = _ts_ms(date.today())
        fig.add_vline(
            x=today_ms,
            line_dash="dot", line_color="#666",
            annotation_text="Today",
            annotation_position="top right",
        )
        # Threshold bands
        for days, color, label in [
            (30,  "rgba(214,39,40,0.06)",  "30d"),
            (60,  "rgba(232,119,34,0.05)", "60d"),
            (90,  "rgba(230,184,0,0.05)",  "90d"),
        ]:
            fig.add_vrect(
                x0=today_ms,
                x1=_ts_ms(date.today() + timedelta(days=days)),
                fillcolor=color, line_width=0,
                annotation_text=label, annotation_position="top left",
            )
        fig.update_layout(
            height=max(320, len(df_time) * 26 + 120),
            margin=dict(l=0, r=20, t=50, b=0),
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig, use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 — RISK MAP
# ─────────────────────────────────────────────────────────────────────────────

with tab_risk:
    col_left, col_right = st.columns([3, 2], gap="large")

    with col_left:
        st.markdown("#### Contract Value vs. Days to Expiry")
        fig_scatter = px.scatter(
            df,
            x="days_left",
            y="value",
            color="urgency",
            size="value",
            size_max=28,
            color_discrete_map=URGENCY_COLOR,
            hover_name="vendor",
            hover_data={
                "category":     True,
                "value_display":True,
                "days_left":    True,
                "urgency":      False,
                "value":        False,
            },
            opacity=0.75,
            labels={
                "days_left": "Days to Expiry",
                "value":     "Contract Value",
                "urgency":   "Urgency",
            },
            category_orders={"urgency": URGENCY_ORDER},
        )
        for days, color, label in [
            (30, "#d62728", "30d"),
            (60, "#e87722", "60d"),
            (90, "#e6b800", "90d"),
        ]:
            fig_scatter.add_vline(
                x=days, line_dash="dash", line_color=color, line_width=1.2,
                annotation_text=label, annotation_position="top",
                annotation_font_color=color,
            )
        fig_scatter.update_layout(
            height=420,
            margin=dict(l=0, r=0, t=20, b=0),
            legend=dict(title="Urgency"),
            yaxis_tickformat=",.0f",
        )
        st.plotly_chart(fig_scatter, use_container_width=True)

    with col_right:
        st.markdown("#### Portfolio Heat Map")
        st.caption("Total contract value by category × urgency bucket")

        pivot = df.pivot_table(
            index="category",
            columns="urgency",
            values="value",
            aggfunc="sum",
            fill_value=0,
        )
        for u in URGENCY_ORDER:
            if u not in pivot.columns:
                pivot[u] = 0
        pivot = pivot[URGENCY_ORDER]

        fig_heat = go.Figure(go.Heatmap(
            z=pivot.values,
            x=pivot.columns.tolist(),
            y=pivot.index.tolist(),
            colorscale=[
                [0.0,  "#eef4ee"],
                [0.3,  "#fffde7"],
                [0.6,  "#fff0e0"],
                [1.0,  "#fde8e8"],
            ],
            hoverongaps=False,
            hovertemplate="<b>%{y}</b> — %{x}<br>Value: %{z:,.0f}<extra></extra>",
            showscale=False,
            text=pivot.values,
            texttemplate="%{text:,.0f}",
            textfont={"size": 10},
        ))
        fig_heat.update_layout(
            height=420,
            margin=dict(l=0, r=0, t=10, b=0),
            xaxis=dict(title="", side="top"),
            yaxis=dict(title="", autorange="reversed"),
        )
        st.plotly_chart(fig_heat, use_container_width=True)

    # summary table under the charts
    st.markdown("#### Flagged contracts at a glance")
    flagged = df[df["urgency"].isin(["Critical", "High"])].sort_values("days_left")
    if flagged.empty:
        st.success("No contracts in the Critical or High urgency buckets under current filters.")
    else:
        cols = ["vendor", "category", "value_display", "expiry_date", "days_left",
                "urgency", "auto_renewal_label"]
        st.dataframe(
            flagged[cols].rename(columns={
                "vendor": "Vendor", "category": "Category",
                "value_display": "Value", "expiry_date": "Expiry",
                "days_left": "Days Left", "urgency": "Urgency",
                "auto_renewal_label": "Auto-Renewal",
            }),
            use_container_width=True,
            hide_index=True,
        )


# ─────────────────────────────────────────────────────────────────────────────
# TAB 4 — MEMOS
# ─────────────────────────────────────────────────────────────────────────────

with tab_memos:
    memos = load_memos()

    if not memos:
        st.info(
            "No memos have been generated yet.  \n"
            "The agent drafts a renegotiation memo for each contract flagged as "
            "Critical or High urgency. Run the agent to generate them."
        )
    else:
        # Always show all memos regardless of sidebar filter
        memo_ids = set(memos.keys())
        df_memo = df_all[df_all["id"].isin(memo_ids)].copy()
        df_memo = df_memo.sort_values("days_left")

        # Summary counts per urgency bucket
        counts = df_memo["urgency"].value_counts()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total memos", len(memo_ids))
        c2.metric("Critical", counts.get("Critical", 0))
        c3.metric("High", counts.get("High", 0))
        c4.metric("Medium", counts.get("Medium", 0))
        st.caption("All memos shown below — click any row to expand the full renegotiation memo.")
        st.divider()

        # Group by urgency bucket so the layout is scannable
        for urgency in URGENCY_ORDER:
            group = df_memo[df_memo["urgency"] == urgency]
            if group.empty:
                continue

            badge_html = f'<span class="badge-{urgency.lower()}">{urgency}</span>'
            st.markdown(
                f"{badge_html} &nbsp; **{len(group)} memo(s)**",
                unsafe_allow_html=True,
            )

            for _, row in group.iterrows():
                cid = row["id"]
                if cid not in memos:
                    continue
                header = (
                    f"{row['vendor']}  ·  {row['value_display']}  ·  "
                    f"Expires {row['expiry_date']} ({row['days_left']}d)  ·  "
                    f"Auto-renewal: {row['auto_renewal_label']}"
                )
                with st.expander(header, expanded=False):
                    st.markdown(memos[cid])

            st.divider()


# ─────────────────────────────────────────────────────────────────────────────
# RUN AGENT (sidebar button handler)
# ─────────────────────────────────────────────────────────────────────────────

if run_btn:
    with agent_placeholder.container():
        with st.spinner("Agent loop running — this may take 1–2 minutes …"):
            # Forward the current process env (which already has the key from
            # config.load_dotenv) so the subprocess never gets a 401 even if
            # its own load_dotenv doesn't find .env from a different cwd.
            subprocess_env = os.environ.copy()
            subprocess_env["PYTHONPATH"] = ROOT
            result = subprocess.run(
                [sys.executable, "main.py", "--mode", "once"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=300,
                env=subprocess_env,
            )
        if result.returncode == 0:
            st.success("Agent completed.")
            output = result.stdout or "(no stdout)"
            st.code(output[-3000:] if len(output) > 3000 else output)
            st.cache_data.clear()
            st.rerun()
        else:
            st.error("Agent exited with errors.")
            err = result.stderr or result.stdout or "(no output)"
            st.code(err[-2000:] if len(err) > 2000 else err)
