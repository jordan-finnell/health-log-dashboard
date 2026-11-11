"""Data: the cleaned daily log as a table."""

import streamlit as st

import shared
from health_log_dashboard import analytics

ctx = shared.page_setup("Data")
daily = shared.load_daily(ctx)

st.title("Data")
days = shared.range_filter()
visible = analytics.last_days(daily, days)

logged = analytics.logged_days(visible)
st.caption(
    f"{len(visible)} days shown · {int(logged.sum())} logged · "
    f"{int((~logged).sum())} with no entry (shown as –, never as zero)."
)
st.dataframe(shared.styled(shared.display_table(visible, ctx.config)), width="stretch", height=520)
