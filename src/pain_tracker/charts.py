"""Plotly figure builders. Pure: no Streamlit imports, theme passed in explicitly.

Design rules (see the ``dataviz`` skill):
- A metric's colour follows the metric (its position in the config), never its rank or
  how many metrics are currently shown.
- One y-axis, always the metric's full 0-10 scale. No dual axes.
- Sequential (one blue hue) for magnitude, diverging blue<->red with a neutral midpoint
  for correlation. Missing is blank, never zero.
- Text wears text tokens, never a series colour.
- Phone friendly: drag/zoom disabled so touch scrolling works; a tap/hover tooltip lists
  every series at that date.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from . import analytics
from .config import Metric

FONT = "system-ui, -apple-system, 'Segoe UI', sans-serif"

# Sequential blue ramp, steps 100 -> 700 (light -> dark).
_BLUE_RAMP = (
    "#cde2fb",
    "#b7d3f6",
    "#9ec5f4",
    "#86b6ef",
    "#6da7ec",
    "#5598e7",
    "#3987e5",
    "#2a78d6",
    "#256abf",
    "#1c5cab",
    "#184f95",
    "#104281",
    "#0d366b",
)

# Chart config for st.plotly_chart: no toolbar, no scroll-zoom, so touch scrolling works.
PLOT_CONFIG = {"displayModeBar": False, "scrollZoom": False, "doubleClick": False}


@dataclass(frozen=True)
class Theme:
    name: str
    surface: str
    text: str
    text_secondary: str
    muted: str
    grid: str
    baseline: str
    series: tuple[str, ...]  # categorical slots 1..8, fixed order
    sequential: tuple[str, ...]  # low -> high magnitude
    div_negative: str
    div_mid: str
    div_positive: str

    def color(self, index: int) -> str:
        if not 0 <= index < len(self.series):
            raise IndexError(f"only {len(self.series)} categorical colours are defined")
        return self.series[index]


LIGHT = Theme(
    name="light",
    surface="#fcfcfb",
    text="#0b0b0b",
    text_secondary="#52514e",
    muted="#898781",
    grid="#e1e0d9",
    baseline="#c3c2b7",
    series=(
        "#2a78d6",
        "#eb6834",
        "#1baf7a",
        "#eda100",
        "#e87ba4",
        "#008300",
        "#6250d6",
        "#e34948",
    ),
    sequential=_BLUE_RAMP,
    div_negative="#2a78d6",
    div_mid="#f0efec",
    div_positive="#e34948",
)

DARK = Theme(
    name="dark",
    surface="#1a1a19",
    text="#f0efec",
    text_secondary="#c3c2b7",
    muted="#898781",
    grid="#2c2c2a",
    baseline="#383835",
    series=(
        "#3987e5",
        "#d95926",
        "#199e70",
        "#c98500",
        "#d55181",
        "#008300",
        "#9085e9",
        "#e66767",
    ),
    # Flipped anchor: low values recede toward the dark surface, high values glow.
    sequential=tuple(reversed(_BLUE_RAMP)),
    div_negative="#3987e5",
    div_mid="#383835",
    div_positive="#e66767",
)


def theme_for(name: str | None) -> Theme:
    return DARK if name == "dark" else LIGHT


# --------------------------------------------------------------------------- helpers


def _rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _mix(a: str, b: str, t: float) -> str:
    ra, rb = _rgb(a), _rgb(b)
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(ra, rb, strict=True))


def _luminance(hex_color: str) -> float:
    def lin(c: int) -> float:
        s = c / 255
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

    r, g, b = (lin(c) for c in _rgb(hex_color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _ink_on(fill: str) -> str:
    """White or near-black text, whichever contrasts better with ``fill``."""
    lum = _luminance(fill)
    on_white = 1.05 / (lum + 0.05)
    on_black = (lum + 0.05) / (_luminance("#0b0b0b") + 0.05)
    return "#ffffff" if on_white >= on_black else "#0b0b0b"


def _colorscale(colors: Sequence[str]) -> list[list]:
    n = len(colors) - 1
    return [[i / n, c] for i, c in enumerate(colors)]


def _layout(theme: Theme, *, height: int, legend: bool, margin: dict | None = None) -> dict:
    return dict(
        height=height,
        margin=margin or dict(l=34, r=12, t=36 if legend else 12, b=32),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT, size=12, color=theme.text_secondary),
        hoverlabel=dict(
            bgcolor=theme.surface,
            bordercolor=theme.baseline,
            font=dict(family=FONT, size=12, color=theme.text),
        ),
        dragmode=False,
        showlegend=legend,
        legend=dict(
            orientation="h",
            x=0,
            y=1.0,
            yanchor="bottom",
            font=dict(color=theme.text_secondary, size=12),
            itemclick=False,
            itemdoubleclick=False,
        ),
    )


def _style_time_axes(fig: go.Figure, theme: Theme, scale: tuple[float, float]) -> None:
    lo, hi = scale
    fig.update_xaxes(
        showgrid=False,
        linecolor=theme.baseline,
        linewidth=1,
        ticks="",
        tickfont=dict(color=theme.muted, size=11),
        tickformat="%b %-d",
        hoverformat="%a %b %-d, %Y",
        fixedrange=True,
        showspikes=True,
        spikemode="across",
        spikesnap="cursor",
        spikethickness=1,
        spikedash="solid",
        spikecolor=theme.muted,
    )
    fig.update_yaxes(
        range=[lo - 0.4, hi + 0.4],
        tickvals=list(range(int(lo), int(hi) + 1, 2)),
        showgrid=True,
        gridcolor=theme.grid,
        gridwidth=1,
        zeroline=False,
        showline=False,
        ticks="",
        tickfont=dict(color=theme.muted, size=11),
        fixedrange=True,
    )


def _colorbar(theme: Theme, tickvals: list, ticktext: list[str], *, top: bool = False) -> dict:
    """Slim horizontal scale. ``top`` puts it above the plot, for charts whose bottom edge
    already carries rotated tick labels or an axis title."""
    return dict(
        orientation="h",
        thickness=8,
        len=0.8,
        x=0.5,
        xanchor="center",
        y=1.06 if top else -0.04,
        yanchor="bottom" if top else "top",
        outlinewidth=0,
        tickvals=tickvals,
        ticktext=ticktext,
        tickfont=dict(color=theme.muted, size=11),
        ticks="",
    )


# ------------------------------------------------------------------------------ trends


def _end_dot(series: pd.Series, color: str, theme: Theme) -> go.Scatter | None:
    valid = series.dropna()
    if valid.empty:
        return None
    return go.Scatter(
        x=[valid.index[-1]],
        y=[valid.iloc[-1]],
        mode="markers",
        marker=dict(size=10, color=color, line=dict(color=theme.surface, width=2)),
        showlegend=False,
        hoverinfo="skip",
    )


def trend_chart(
    daily: pd.DataFrame,
    metric: Metric,
    theme: Theme,
    color_index: int,
    *,
    days: int | None = None,
    show_30d: bool = False,
    height: int = 300,
) -> go.Figure:
    """One metric: faint daily dots, a 2px 7-day average, optionally a 30-day average."""
    color = theme.color(color_index)
    raw = daily[metric.key]
    avg7 = analytics.rolling_mean(raw, 7)
    avg30 = analytics.rolling_mean(raw, 30)
    raw, avg7, avg30 = (analytics.last_days(s, days) for s in (raw, avg7, avg30))

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=raw.index,
            y=raw,
            mode="markers",
            name="Daily",
            marker=dict(size=6, color=color, opacity=0.4),
            hovertemplate="%{y:.0f}<extra>Daily</extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=avg7.index,
            y=avg7,
            mode="lines",
            name="7-day avg",
            line=dict(color=color, width=2, shape="spline", smoothing=0.5),
            hovertemplate="%{y:.1f}<extra>7-day avg</extra>",
        )
    )
    if show_30d:
        fig.add_trace(
            go.Scatter(
                x=avg30.index,
                y=avg30,
                mode="lines",
                name="30-day avg",
                line=dict(color=theme.text_secondary, width=2),
                hovertemplate="%{y:.1f}<extra>30-day avg</extra>",
            )
        )
    if (dot := _end_dot(avg7, color, theme)) is not None:
        fig.add_trace(dot)

    fig.update_layout(**_layout(theme, height=height, legend=True), hovermode="x unified")
    _style_time_axes(fig, theme, (metric.min, metric.max))
    return fig


def overlay_chart(
    daily: pd.DataFrame,
    selected: Sequence[Metric],
    all_metrics: Sequence[Metric],
    theme: Theme,
    *,
    days: int | None = None,
    height: int = 340,
) -> go.Figure:
    """Several metrics' 7-day averages on one shared 0-10 axis.

    Colours come from each metric's position in ``all_metrics``, so they never change as
    the selection changes. Up to four series are also labelled at the line end (in text ink,
    skipping labels that would collide); the legend is always shown.
    """
    order = {m.key: i for i, m in enumerate(all_metrics)}
    lo = min(m.min for m in selected)
    hi = max(m.max for m in selected)

    fig = go.Figure()
    ends: list[tuple[float, pd.Timestamp, str]] = []
    extent: list[pd.Timestamp] = []
    for m in selected:
        color = theme.color(order[m.key])
        avg7 = analytics.last_days(analytics.rolling_mean(daily[m.key], 7), days)
        if len(avg7):
            extent += [avg7.index.min(), avg7.index.max()]
        fig.add_trace(
            go.Scatter(
                x=avg7.index,
                y=avg7,
                mode="lines",
                name=m.label,
                line=dict(color=color, width=2, shape="spline", smoothing=0.5),
                hovertemplate="%{y:.1f}<extra>" + m.label + "</extra>",
            )
        )
        if (dot := _end_dot(avg7, color, theme)) is not None:
            fig.add_trace(dot)
            valid = avg7.dropna()
            ends.append((float(valid.iloc[-1]), valid.index[-1], m.label))

    label_ends = len(selected) <= 4
    if label_ends:
        placed: list[float] = []
        for y, x, label in sorted(ends, reverse=True):
            if any(abs(y - p) < 0.7 for p in placed):
                continue  # would collide; the legend and tooltip carry this one
            placed.append(y)
            fig.add_annotation(
                x=x,
                y=y,
                text=label,
                showarrow=False,
                xanchor="left",
                xshift=10,
                font=dict(color=theme.text_secondary, size=11),
            )

    margin = dict(l=34, r=96 if label_ends else 12, t=36, b=32)
    fig.update_layout(
        **_layout(theme, height=height, legend=len(selected) >= 2, margin=margin),
        hovermode="x unified",
    )
    _style_time_axes(fig, theme, (lo, hi))
    if extent:  # pin to the data so end labels sit in the margin instead of stretching the axis
        fig.update_xaxes(range=[min(extent), max(extent) + pd.Timedelta(days=1)])
    return fig


# ---------------------------------------------------------------------------- calendar


def _week_labels(weeks: pd.Index) -> list[str]:
    labels = [f"{w:%b} {w.day}" for w in weeks]
    if len(set(labels)) != len(labels):  # log spans more than a year
        labels = [f"{w:%b} {w.day} '{w:%y}" for w in weeks]
    return labels


def calendar_chart(series: pd.Series, metric: Metric, theme: Theme) -> go.Figure:
    """Weeks x weekdays heatmap, newest week on top. Blank = no entry (never zero)."""
    values, in_range = analytics.calendar_grid(series)
    weeks = _week_labels(values.index)

    dates = np.array(
        [[w + pd.Timedelta(days=d) for d in range(7)] for w in values.index], dtype=object
    )
    hover = np.vectorize(lambda d: f"{d:%a} {d:%b} {d.day}, {d.year}", otypes=[str])(dates)

    base = np.where(in_range.to_numpy(), 1.0, np.nan)
    fig = go.Figure()
    # Faint cell for every in-range day, so days with no entry still read as "no entry".
    fig.add_trace(
        go.Heatmap(
            z=base,
            x=analytics.WEEKDAYS,
            y=weeks,
            colorscale=[[0, theme.grid], [1, theme.grid]],
            showscale=False,
            xgap=2,
            ygap=2,
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Heatmap(
            z=values.to_numpy(),
            x=analytics.WEEKDAYS,
            y=weeks,
            customdata=hover,
            zmin=metric.min,
            zmax=metric.max,
            colorscale=_colorscale(theme.sequential),
            xgap=2,
            ygap=2,
            hoverongaps=False,
            hovertemplate="%{customdata}<br><b>%{z:.0f}</b><extra></extra>",
            colorbar=_colorbar(
                theme,
                [metric.min, (metric.min + metric.max) / 2, metric.max],
                [f"{metric.min:g}", f"{(metric.min + metric.max) / 2:g}", f"{metric.max:g}"],
            ),
        )
    )
    height = max(240, 22 * len(weeks) + 110)
    fig.update_layout(
        **_layout(theme, height=height, legend=False, margin=dict(l=56, r=12, t=28, b=60))
    )
    fig.update_xaxes(
        side="top",
        showgrid=False,
        ticks="",
        tickfont=dict(color=theme.muted, size=11),
        fixedrange=True,
        showline=False,
    )
    fig.update_yaxes(
        type="category",
        showgrid=False,
        ticks="",
        tickfont=dict(color=theme.muted, size=11),
        fixedrange=True,
        showline=False,
    )
    return fig


# ---------------------------------------------------------------------------- patterns


def correlation_chart(corr: pd.DataFrame, metrics: Sequence[Metric], theme: Theme) -> go.Figure:
    """Lower-triangle correlation matrix, diverging blue (negative) <-> red (positive).

    Only the stronger relationships (|r| >= 0.4) are labelled; the tooltip and the table
    view carry the rest.
    """
    keys = [m.key for m in metrics]
    labels = [m.label for m in metrics]
    r = corr.reindex(index=keys, columns=keys).to_numpy(dtype="float64")
    # Each pair appears once and the diagonal is dropped, so the first row and last column
    # (which would be empty) are omitted: rows are metrics[1:], columns are metrics[:-1].
    row_labels, col_labels = labels[1:], labels[:-1]
    r = r[1:, :-1]
    mask = np.tril(np.ones_like(r, dtype=bool))
    z = np.where(mask, r, np.nan)

    fig = go.Figure(
        go.Heatmap(
            z=z,
            x=col_labels,
            y=row_labels,
            zmin=-1,
            zmax=1,
            colorscale=_colorscale([theme.div_negative, theme.div_mid, theme.div_positive]),
            xgap=2,
            ygap=2,
            hoverongaps=False,
            hovertemplate="%{y} × %{x}<br>r = <b>%{z:.2f}</b><extra></extra>",
            colorbar=_colorbar(theme, [-1, 0, 1], ["−1", "0", "+1"], top=True),
        )
    )
    for i, j in zip(*np.nonzero(mask), strict=True):
        value = r[i, j]
        if np.isnan(value) or abs(value) < 0.4:
            continue
        end = theme.div_positive if value > 0 else theme.div_negative
        fill = _mix(theme.div_mid, end, abs(value))
        fig.add_annotation(
            x=col_labels[j],
            y=row_labels[i],
            text=f"{value:+.2f}",
            showarrow=False,
            font=dict(size=11, color=_ink_on(fill)),
        )
    height = 64 * (len(metrics) - 1) + 160
    fig.update_layout(
        **_layout(theme, height=height, legend=False, margin=dict(l=96, r=12, t=64, b=96))
    )
    # Fixed angle: the text ends at its tick, so the last label can't run off the right edge.
    fig.update_xaxes(
        showgrid=False,
        ticks="",
        tickangle=-40,
        tickfont=dict(color=theme.muted, size=11),
        fixedrange=True,
    )
    fig.update_yaxes(
        autorange="reversed",
        showgrid=False,
        ticks="",
        tickfont=dict(color=theme.muted, size=11),
        fixedrange=True,
    )
    return fig


def weekday_chart(
    profile: pd.DataFrame, metric: Metric, theme: Theme, color_index: int, *, height: int = 280
) -> go.Figure:
    """Mean rating by weekday: one hue, thin bars, value at the tip."""
    values = profile[metric.key]
    fig = go.Figure(
        go.Bar(
            x=list(values.index),
            y=values.to_numpy(),
            width=0.4,
            marker=dict(color=theme.color(color_index), cornerradius=4),
            text=[("" if pd.isna(v) else f"{v:.1f}") for v in values],
            textposition="outside",
            textfont=dict(color=theme.text, size=12),
            cliponaxis=False,
            hovertemplate="%{x}: <b>%{y:.1f}</b> average<extra></extra>",
        )
    )
    fig.update_layout(
        **_layout(theme, height=height, legend=False, margin=dict(l=34, r=12, t=24, b=32))
    )
    fig.update_xaxes(
        showgrid=False,
        linecolor=theme.baseline,
        ticks="",
        tickfont=dict(color=theme.muted, size=11),
        fixedrange=True,
    )
    fig.update_yaxes(
        range=[metric.min, metric.max],
        tickvals=list(range(int(metric.min), int(metric.max) + 1, 2)),
        showgrid=True,
        gridcolor=theme.grid,
        gridwidth=1,
        zeroline=False,
        ticks="",
        tickfont=dict(color=theme.muted, size=11),
        fixedrange=True,
    )
    return fig


def pair_chart(counts: pd.DataFrame, x: Metric, y: Metric, theme: Theme) -> go.Figure:
    """How many days each combination of two ratings occurred (sequential, blank = never)."""
    z = counts.to_numpy(dtype="float64")
    base = np.ones_like(z)
    z = np.where(z > 0, z, np.nan)
    xs, ys = list(counts.index), list(counts.columns)  # x metric on the x axis

    fig = go.Figure()
    fig.add_trace(
        go.Heatmap(
            z=base.T,
            x=xs,
            y=ys,
            colorscale=[[0, theme.grid], [1, theme.grid]],
            showscale=False,
            xgap=2,
            ygap=2,
            hoverinfo="skip",
        )
    )
    top = int(np.nanmax(z)) if np.isfinite(z).any() else 1
    fig.add_trace(
        go.Heatmap(
            z=z.T,
            x=xs,
            y=ys,
            zmin=1,
            zmax=max(top, 2),
            colorscale=_colorscale(theme.sequential),
            xgap=2,
            ygap=2,
            hoverongaps=False,
            hovertemplate=(
                f"{x.label} %{{x}} · {y.label} %{{y}}<br><b>%{{z:.0f}}</b> days<extra></extra>"
            ),
            colorbar=_colorbar(theme, [1, max(top, 2)], ["1 day", f"{max(top, 2)} days"], top=True),
        )
    )
    fig.update_layout(
        **_layout(theme, height=400, legend=False, margin=dict(l=48, r=12, t=64, b=56))
    )
    fig.update_xaxes(
        title=dict(text=x.label, font=dict(color=theme.text_secondary, size=12)),
        type="category",
        showgrid=False,
        ticks="",
        tickfont=dict(color=theme.muted, size=11),
        fixedrange=True,
    )
    fig.update_yaxes(
        title=dict(text=y.label, font=dict(color=theme.text_secondary, size=12)),
        type="category",
        showgrid=False,
        ticks="",
        tickfont=dict(color=theme.muted, size=11),
        fixedrange=True,
    )
    return fig
