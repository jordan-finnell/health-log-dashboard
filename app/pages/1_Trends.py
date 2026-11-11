"""Trends: each metric over time, with 7- and 30-day rolling averages."""

import streamlit as st

import shared
from pain_tracker import analytics, charts

ctx = shared.page_setup("Trends")
daily = shared.load_daily(ctx)
metrics = ctx.config.metrics
by_key = {m.key: m for m in metrics}

st.title("Trends")
days = shared.range_filter()

picked = st.multiselect(
    "Metrics",
    options=[m.key for m in metrics],
    default=[metrics[0].key],
    format_func=lambda k: by_key[k].label,
)
if not picked:
    st.info("Pick at least one metric.")
    st.stop()
selected = [by_key[k] for k in picked]

if len(selected) == 1:
    show_30 = st.toggle("Show 30-day average", value=False)
    shared.show_chart(
        charts.trend_chart(
            daily,
            selected[0],
            ctx.theme,
            ctx.color_index[selected[0].key],
            days=days,
            show_30d=show_30,
        )
    )
else:
    view = st.segmented_control(
        "View",
        ["Overlay", "Separate"],
        default="Overlay",
        required=True,
        key="trend_view",
    )
    if view == "Overlay":
        st.caption("7-day averages on one shared 0–10 axis.")
        shared.show_chart(charts.overlay_chart(daily, selected, metrics, ctx.theme, days=days))
    else:
        for m in selected:
            st.subheader(m.label, divider=False)
            shared.show_chart(
                charts.trend_chart(
                    daily, m, ctx.theme, ctx.color_index[m.key], days=days, height=240
                ),
                key=f"trend_{m.key}",
            )

shared.table_view(analytics.last_days(daily[picked], days), ctx.config)
