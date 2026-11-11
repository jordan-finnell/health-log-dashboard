"""Overview: one stat tile per metric (7-day average vs the 7 days before) plus logging stats."""

import math

import streamlit as st

import shared
from health_log_dashboard import analytics

ctx = shared.page_setup("Overview")
daily = shared.load_daily(ctx)

st.title("Health Log Dashboard")
last = daily.index.max()
st.caption(f"Last entry {last:%b} {last.day}, {last.year} · {len(daily)} days in the log")

st.subheader("Last 7 days")
st.caption("Average rating, compared with the 7 days before. Sparkline is the last 30 days.")


def tile_slots(n: int):
    """One slot per metric, filled row by row so that when Streamlit stacks the two columns
    on a phone the tiles still read in config order."""
    for start in range(0, n, 2):
        row = st.columns(2)
        yield from row[: min(2, n - start)]


for metric, slot in zip(ctx.config.metrics, tile_slots(len(ctx.config.metrics)), strict=True):
    series = daily[metric.key]
    cmp = analytics.period_comparison(series, 7)
    spark = analytics.rolling_mean(series, 7).iloc[-30:].dropna()
    newest = analytics.latest(series)

    value = "–" if math.isnan(cmp.current) else f"{cmp.current:.1f}"
    if math.isnan(cmp.delta):
        delta = None
    elif abs(cmp.delta) < 0.05:
        delta = "0.0"
    else:
        delta = f"{cmp.delta:+.1f}"

    with slot:
        st.metric(
            metric.label,
            value,
            delta=delta,
            # Rating up is bad for most metrics, so flip the colour for those.
            delta_color="normal" if metric.higher_is_better else "inverse",
            delta_description="vs prior 7 days",
            chart_data=spark if len(spark) > 1 else None,
            chart_type="line",
            border=True,
        )
        if newest is not None:
            when, rating = newest
            st.caption(f"Latest {rating:.0f} · {when:%b} {when.day}")

st.subheader("Logging")
streak = analytics.logging_streak(daily, as_of=None)
a, b, c = st.columns(3)
a.metric("Current streak", f"{streak.current} d")
b.metric("Longest streak", f"{streak.longest} d")
rate = analytics.completion_rate(daily, days=30)
c.metric("Last 30 days", "–" if math.isnan(rate) else f"{rate:.0%}")
