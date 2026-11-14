"""Overview: one stat tile per metric (7-day average vs the 7 days before) plus logging stats."""

import math

import streamlit as st
import winds_of_change as woc

import shared
from health_log_dashboard import analytics, charts
from health_log_dashboard.weather import DISPLAY_UNITS, FACTOR_KEYS, SHORT_LABELS

ctx = shared.page_setup("Overview")
daily = shared.load_daily(ctx)

st.title("Health Log Dashboard")
last = daily.index.max()
st.caption(f"Last entry {last:%b} {last.day}, {last.year} · {len(daily)} days in the log")

st.subheader("Last 7 days")
st.caption(
    "Average rating, compared with the 7 days before. The sparkline plots each day's rating "
    "over the last 30 days; tap it to see the date."
)


def tile_slots(n: int):
    """One slot per metric, filled row by row so that when Streamlit stacks the two columns
    on a phone the tiles still read in config order."""
    for start in range(0, n, 2):
        row = st.columns(2)
        yield from row[: min(2, n - start)]


for metric, slot in zip(ctx.config.metrics, tile_slots(len(ctx.config.metrics)), strict=True):
    series = daily[metric.key]
    cmp = analytics.period_comparison(series, 7)
    newest = analytics.latest(series)

    value = "–" if math.isnan(cmp.current) else f"{cmp.current:.1f}"
    if math.isnan(cmp.delta):
        delta = None
    elif abs(cmp.delta) < 0.05:
        delta = "0.0"
    else:
        delta = f"{cmp.delta:+.1f}"

    if math.isnan(cmp.delta) or abs(cmp.delta) < 0.05:
        spark_color = ctx.theme.muted
    else:
        spark_color = (
            charts.STATUS_GOOD if (cmp.delta > 0) == metric.higher_is_better else charts.STATUS_BAD
        )

    with slot:
        with st.container(border=True):
            st.metric(
                metric.label,
                value,
                delta=delta,
                # Rating up is bad for most metrics, so flip the colour for those.
                delta_color="normal" if metric.higher_is_better else "inverse",
                delta_description="vs prior 7 days",
            )
            if series.notna().sum() > 1:
                shared.show_chart(
                    charts.sparkline_chart(series, ctx.theme, spark_color),
                    key=f"spark_{metric.key}",
                )
        if newest is not None:
            when, rating = newest
            st.caption(f"Latest {rating:.0f} · {when:%b} {when.day}")

weather = shared.load_weather(ctx, daily, quiet=True)
if weather is not None:
    lines = []
    for key in FACTOR_KEYS:
        look = weather.outlook(key, 24)
        if look is None or math.isnan(look.next):
            continue
        unit = DISPLAY_UNITS.unit_for(woc.factor(key))
        if abs(look.next) < 0.5:
            line = f"{SHORT_LABELS[key]}: steady"
        else:
            arrow = "↑" if look.next > 0 else "↓"
            line = f"{SHORT_LABELS[key]} {arrow} {abs(look.next):.0f} {unit}"
        if not math.isnan(look.next_percentile):
            line += f" · larger than {look.next_percentile:.0%} of past changes"
            if look.next_percentile >= 0.8:
                line = f"**{line}**"
        lines.append(f"- {line}")
    if lines:
        with st.container(border=True):
            st.markdown("**Weather · next 24 h**\n\n" + "\n".join(lines))
            st.page_link("pages/4_Weather.py", label="Weather patterns", icon=":material/air:")

st.subheader("Logging")
streak = analytics.logging_streak(daily, as_of=None)
a, b, c = st.columns(3)
a.metric("Current streak", f"{streak.current} d")
b.metric("Longest streak", f"{streak.longest} d")
rate = analytics.completion_rate(daily, days=30)
c.metric("Last 30 days", "–" if math.isnan(rate) else f"{rate:.0%}")
