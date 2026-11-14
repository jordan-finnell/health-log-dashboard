"""Weather: do ratings move with changes in pressure, humidity or temperature?"""

import math

import pandas as pd
import streamlit as st
import winds_of_change as woc

import shared
from health_log_dashboard import analytics, charts
from health_log_dashboard.weather import (
    DEFAULT_WINDOW,
    DISPLAY_UNITS,
    FACTOR_KEYS,
    SHORT_LABELS,
    WINDOWS,
)

MIN_DAYS = 60
LAGS = {0: "Same day", 1: "Next day"}

ctx = shared.page_setup("Weather", icon=":material/air:")
daily = shared.load_daily(ctx)
metrics = ctx.config.metrics
by_key = {m.key: m for m in metrics}
labels = {m.key: m.label for m in metrics}

st.title("Weather")
wx = shared.load_weather(ctx, daily)
if wx is None:
    st.stop()

factor_key = st.segmented_control(
    "Weather factor",
    list(FACTOR_KEYS),
    format_func=SHORT_LABELS.get,
    default="pressure",
    required=True,
    key="weather_factor",
    persist_state="session",
    label_visibility="collapsed",
    width="stretch",
)
hours = st.segmented_control(
    "Change over",
    list(WINDOWS),
    format_func=lambda h: f"{h}h",
    default=DEFAULT_WINDOW,
    required=True,
    key="weather_window",
    persist_state="session",
    label_visibility="collapsed",
    width="stretch",
)
factor = woc.factor(factor_key)
unit = DISPLAY_UNITS.unit_for(factor)
name = SHORT_LABELS[factor_key]
st.caption(
    f"{factor.description} Each day is summarised by its biggest {hours}-hour change, up or down."
)

# --- Outlook ----------------------------------------------------------------------------
look = wx.outlook(factor_key, hours)


def _line(title: str, value: float, pct: float) -> str:
    if math.isnan(value):
        return f"{title}: not available yet"
    text = f"{title}: {value:+.1f} {unit}"
    if not math.isnan(pct):
        text += f" · larger than {pct:.0%} of past changes"
        if pct >= 0.8:
            text = f"**{text}**"
    return text


if look is not None:
    with st.container(border=True):
        st.markdown(
            f"- {_line(f'Last {hours} h', look.last, look.last_percentile)}\n"
            f"- {_line(f'Next {hours} h (forecast)', look.next, look.next_percentile)}"
        )

# --- Heatmap ----------------------------------------------------------------------------
change = wx.daily[woc.change_column(factor_key, hours)].reindex(daily.index)
bins = woc.change_bins(change)
anoms = woc.anomaly(daily[[m.key for m in metrics]])

st.subheader("On big-change days")
if daily.notna().any(axis=1).sum() < MIN_DAYS or math.isnan(bins.drop_below):
    st.info(f"This needs at least {MIN_DAYS} logged days with weather. Check back later.")
    st.stop()
lag = st.segmented_control(
    "Ratings on",
    list(LAGS),
    format_func=LAGS.get,
    default=0,
    required=True,
    key="weather_lag",
    label_visibility="collapsed",
)
st.caption(
    f"Big drop: {bins.drop_below:+.1f} {unit} or lower within {hours} h. Big rise: "
    f"{bins.rise_above:+.1f} {unit} or higher. Those are the steepest 20% of days each way, "
    "over the whole log. Each cell compares ratings with that metric's usual level around then "
    "(±2 weeks): red is worse, blue better. Numbers mark differences that stand out from "
    "day-to-day noise. A rough guide, not proof: with this many combinations to try, some "
    "cells light up by chance."
)
response = woc.response_by_change(anoms, change, bins, lag=lag)
shared.show_chart(charts.weather_response_chart(response, metrics, ctx.theme))
with st.expander("Table view", icon=":material/table:"):
    table = response.assign(metric=response["metric"].map(labels))
    table = table.pivot(index="metric", columns="bin", values=["mean", "n"])
    table = table.reindex(index=[m.label for m in metrics])
    table.columns = [f"{b} ({'days' if v == 'n' else 'vs usual'})" for v, b in table.columns]
    st.dataframe(table.round(2), width="stretch")

# --- Event profile ----------------------------------------------------------------------
st.subheader("Around a big change")
key = st.selectbox("Metric", list(by_key), format_func=labels.get, key="weather_metric")
metric = by_key[key]
drops = woc.event_profile(anoms[key], change, bins, "drop")
rises = woc.event_profile(anoms[key], change, bins, "rise")
if drops["mean"].isna().all() and rises["mean"].isna().all():
    st.info("Not enough big changes in the log yet to average.")
else:
    st.caption(
        f"{metric.label} compared with usual, from 2 days before to 3 days after the first day "
        "of each big change (the legend gives the number of events). Whiskers are 95% "
        "intervals. Days before are context, not a control: weather often starts turning "
        "a day early."
    )
    shared.show_chart(
        charts.event_profile_chart(drops, rises, metric, ctx.theme, ctx.color_index[key])
    )
    with st.expander("Table view", icon=":material/table:"):
        both = pd.concat({"After big drops": drops, "After big rises": rises}, axis=1)
        both.index.name = "Days from change"
        st.dataframe(both.round(2), width="stretch")

# --- Timeline ---------------------------------------------------------------------------
st.subheader(f"Day by day: {metric.label}")
days = shared.range_filter(("30d", "90d", "1y"), default="90d")
change_label = f"{name}, {hours} h change"
shared.show_chart(
    charts.weather_timeline_chart(
        daily[key],
        change,
        metric,
        ctx.theme,
        ctx.color_index[key],
        change_label=change_label,
        unit=unit,
        drop_below=bins.drop_below,
        rise_above=bins.rise_above,
        days=days,
    )
)
st.caption("Darker bars are big-change days. Tap a day to see both panels.")
with st.expander("Table view", icon=":material/table:"):
    side = pd.DataFrame({metric.label: daily[key], f"{change_label} ({unit})": change})
    side = analytics.last_days(side, days).sort_index(ascending=False)
    side.index = side.index.strftime("%Y-%m-%d")
    st.dataframe(side.round(1), width="stretch")

if wx.synthetic:
    st.caption("Demo mode: synthetic weather, invented for illustration.")
else:
    st.caption(
        "Weather data by [Open-Meteo.com](https://open-meteo.com/) (CC BY 4.0), ECMWF IFS model."
    )
