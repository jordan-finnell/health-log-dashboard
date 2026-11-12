"""Trends: each metric over time, with a rolling average over an adjustable window."""

import streamlit as st

import shared
from health_log_dashboard import analytics, charts

ctx = shared.page_setup("Trends")
daily = shared.load_daily(ctx)
metrics = ctx.config.metrics
by_key = {m.key: m for m in metrics}

st.title("Trends")
days = shared.range_filter()
window = st.slider(
    "Rolling average window (days)",
    min_value=1,
    max_value=30,
    value=7,
    key="trend_window",
    persist_state="session",
)

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
    shared.show_chart(
        charts.trend_chart(
            daily,
            selected[0],
            ctx.theme,
            ctx.color_index[selected[0].key],
            days=days,
            window=window,
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
        st.caption(
            f"{window}-day averages on one shared 0–10 axis."
            if window > 1
            else "Daily ratings on one shared 0–10 axis."
        )
        shared.show_chart(
            charts.overlay_chart(daily, selected, metrics, ctx.theme, days=days, window=window)
        )
    else:
        for m in selected:
            st.subheader(m.label, divider=False)
            shared.show_chart(
                charts.trend_chart(
                    daily,
                    m,
                    ctx.theme,
                    ctx.color_index[m.key],
                    days=days,
                    window=window,
                    height=240,
                ),
                key=f"trend_{m.key}",
            )

shared.table_view(analytics.last_days(daily[picked], days), ctx.config)
