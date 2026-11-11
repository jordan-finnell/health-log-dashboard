"""Calendar: weeks x weekdays heatmap per metric, plus logging consistency."""

import math

import streamlit as st

import shared
from pain_tracker import analytics, charts

ctx = shared.page_setup("Calendar")
daily = shared.load_daily(ctx)
metrics = ctx.config.metrics
by_key = {m.key: m for m in metrics}

st.title("Calendar")
days = shared.range_filter(("30d", "90d", "1y", "All"))

key = st.selectbox("Metric", [m.key for m in metrics], format_func=lambda k: by_key[k].label)
metric = by_key[key]
visible = analytics.last_days(daily, days)

st.caption(
    "Darker blue means a higher rating. Grey cells are days with no entry. Newest week on top."
)
shared.show_chart(charts.calendar_chart(visible[key], metric, ctx.theme))

streak = analytics.logging_streak(visible)
rate = analytics.completion_rate(visible)
a, b, c = st.columns(3)
a.metric("Current streak", f"{streak.current} d")
b.metric("Longest streak", f"{streak.longest} d")
c.metric("Days logged", "–" if math.isnan(rate) else f"{rate:.0%}")

values, _ = analytics.calendar_grid(visible[key])
with st.expander("Table view", icon=":material/table:"):
    table = values.sort_index(ascending=False)
    table.index = table.index.strftime("Week of %b %-d")
    st.dataframe(table, width="stretch")
