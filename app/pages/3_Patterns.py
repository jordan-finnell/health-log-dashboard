"""Patterns: correlations, weekday profile, and how pairs of ratings co-occur."""

import streamlit as st

import shared
from health_log_dashboard import analytics, charts

MIN_DAYS = 14

ctx = shared.page_setup("Patterns")
daily = shared.load_daily(ctx)
metrics = ctx.config.metrics
by_key = {m.key: m for m in metrics}
labels = {m.key: m.label for m in metrics}

st.title("Patterns")
days = shared.range_filter(("30d", "90d", "1y", "All"), default="All")
visible = analytics.last_days(daily, days)

if visible.notna().any(axis=1).sum() < MIN_DAYS:
    st.info(f"Patterns need at least {MIN_DAYS} logged days in range. Try a longer range.")
    st.stop()

# --- Correlations ---------------------------------------------------------------------
st.subheader("How metrics move together")
st.caption(
    "Spearman correlation between daily ratings. Red: rise together. Blue: move in opposite "
    "directions. Only |r| ≥ 0.4 is labelled. Pairs with fewer than "
    f"{MIN_DAYS} shared days are left blank. This shows association, not cause."
)
corr = analytics.correlation_matrix(visible, min_periods=MIN_DAYS)
shared.show_chart(charts.correlation_chart(corr, metrics, ctx.theme))
with st.expander("Table view", icon=":material/table:"):
    st.dataframe(corr.rename(index=labels, columns=labels).round(2), width="stretch")

# --- Weekday profile ------------------------------------------------------------------
st.subheader("Rating by weekday")
st.caption(
    "Each faint dot is one day. The thick line spans the middle half of days (25th to 75th "
    "percentile) and the ringed dot is the average. Tap for details."
)
wd_key = st.selectbox("Metric", list(by_key), format_func=labels.get, key="weekday_metric")
wd_series = visible[wd_key]
shared.show_chart(
    charts.weekday_chart(wd_series, by_key[wd_key], ctx.theme, ctx.color_index[wd_key])
)
with st.expander("Table view", icon=":material/table:"):
    table = analytics.weekday_summary(wd_series).rename(
        columns={
            "n": "Days",
            "mean": "Average",
            "median": "Median",
            "q25": "25th pct",
            "q75": "75th pct",
            "min": "Min",
            "max": "Max",
        }
    )
    st.dataframe(table.round(1), width="stretch")

# --- Pair co-occurrence ---------------------------------------------------------------
st.subheader("Two ratings side by side")
st.caption("How many days each combination of ratings occurred. Blank cells never happened.")
keys = list(by_key)
c1, c2 = st.columns(2)
x_key = c1.selectbox("Horizontal", keys, index=0, format_func=labels.get, key="pair_x")
y_key = c2.selectbox(
    "Vertical", keys, index=min(1, len(keys) - 1), format_func=labels.get, key="pair_y"
)
if x_key == y_key:
    st.info("Pick two different metrics.")
else:
    x, y = by_key[x_key], by_key[y_key]
    counts = analytics.pair_counts(visible, x_key, y_key, int(x.min), int(x.max))
    shared.show_chart(charts.pair_chart(counts, x, y, ctx.theme))
    with st.expander("Table view", icon=":material/table:"):
        st.dataframe(counts.rename_axis(index=x.label, columns=y.label), width="stretch")
