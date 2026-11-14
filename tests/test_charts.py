import numpy as np
import pandas as pd
import pytest

from health_log_dashboard import analytics, charts
from health_log_dashboard.synthetic import generate_raw
from health_log_dashboard.transform import to_daily

from .conftest import FIXED_END

THEMES = [charts.LIGHT, charts.DARK]


@pytest.fixture(scope="module")
def daily(config):
    return to_daily(generate_raw(config, days=150, end=FIXED_END, seed=11), config)


def trace_color(fig, name):
    trace = next(t for t in fig.data if t.name == name)
    return trace.line.color


@pytest.mark.parametrize("theme", THEMES, ids=lambda t: t.name)
class TestEveryChartBuilds:
    def test_trend(self, daily, config, theme):
        m = config.metrics[0]
        fig = charts.trend_chart(daily, m, theme, 0, days=60, window=30)
        names = [t.name for t in fig.data]
        assert {"Daily", "30-day avg"} <= set(names)
        assert fig.layout.dragmode is False
        assert list(fig.layout.yaxis.range) == [m.min - 0.4, m.max + 0.4]

    def test_sparkline(self, daily, config, theme):
        series = daily["headache"]
        fig = charts.sparkline_chart(series, theme, charts.STATUS_GOOD)
        (trace,) = fig.data
        # plots the actual daily values (not an average) for the last 30 days, with dates
        expected = series.iloc[-30:]
        assert list(trace.x) == list(expected.index)
        np.testing.assert_array_equal(np.asarray(trace.y, dtype=float), expected.to_numpy())
        assert "%{x|" in trace.hovertemplate and "%{y" in trace.hovertemplate
        assert fig.layout.xaxis.visible is False and fig.layout.yaxis.visible is False

    def test_overlay(self, daily, config, theme):
        fig = charts.overlay_chart(daily, config.metrics[:3], config.metrics, theme)
        assert fig.layout.showlegend is True
        assert fig.layout.hovermode == "x unified"

    def test_calendar(self, daily, config, theme):
        fig = charts.calendar_chart(daily["headache"], config.by_key("headache"), theme)
        data = fig.data[1]
        assert data.zmin == 0 and data.zmax == 10
        # missing days stay missing: never plotted as zero
        assert np.isnan(np.array(data.z, dtype=float)).any()

    def test_correlation(self, daily, config, theme):
        corr = analytics.correlation_matrix(daily)
        fig = charts.correlation_chart(corr, config.metrics, theme)
        z = np.array(fig.data[0].z, dtype=float)
        assert np.isnan(
            z[np.triu_indices_from(z, k=1)]
        ).all()  # upper triangle hidden (each pair shown once)
        assert fig.data[0].zmin == -1 and fig.data[0].zmax == 1

    def test_weekday(self, daily, config, theme):
        m = config.metrics[0]
        fig = charts.weekday_chart(daily[m.key], m, theme, 0)
        names = [t.name for t in fig.data]
        assert names == ["Each day", "Middle half", "Average"]
        assert list(fig.layout.xaxis.ticktext) == analytics.WEEKDAYS
        # one dot per logged day, kept within its weekday's column
        dots = fig.data[0]
        assert len(dots.x) == daily[m.key].notna().sum()
        assert (np.abs(np.asarray(dots.x) - np.round(np.asarray(dots.x))) <= 0.25).all()

    def test_pair(self, daily, config, theme):
        x, y = config.metrics[0], config.metrics[1]
        counts = analytics.pair_counts(daily, x.key, y.key)
        fig = charts.pair_chart(counts, x, y, theme)
        zero_cells = np.isnan(np.array(fig.data[1].z, dtype=float)).sum()
        assert zero_cells == (counts.to_numpy() == 0).sum()  # never-occurred combos are blank


def test_colour_follows_the_metric_not_the_selection(daily, config):
    """Selecting fewer metrics must not repaint the survivors."""
    anxiety = config.by_key("anxiety")
    alone = charts.overlay_chart(
        daily, [anxiety, config.by_key("excitement")], config.metrics, charts.LIGHT
    )
    with_more = charts.overlay_chart(daily, config.metrics, config.metrics, charts.LIGHT)
    assert trace_color(alone, "Anxiety") == trace_color(with_more, "Anxiety")
    assert trace_color(alone, "Anxiety") == charts.LIGHT.color(3)


def test_trend_chart_uses_the_same_colour_as_overlay(daily, config):
    m = config.by_key("depression")
    idx = [x.key for x in config.metrics].index("depression")
    single = charts.trend_chart(daily, m, charts.DARK, idx)
    overlay = charts.overlay_chart(daily, config.metrics, config.metrics, charts.DARK)
    assert trace_color(single, "7-day avg") == trace_color(overlay, "Depression")


def test_overlay_has_no_line_end_labels_and_keeps_the_legend(daily, config):
    """The legend names the series; end labels were dropped to save phone screen width."""
    for n in (2, 3, len(config.metrics)):
        fig = charts.overlay_chart(daily, config.metrics[:n], config.metrics, charts.LIGHT)
        assert len(fig.layout.annotations) == 0
        assert fig.layout.showlegend is True
        assert fig.layout.margin.r <= 16


def test_charts_handle_a_metric_with_no_data(config):
    idx = pd.date_range("2026-01-01", periods=30, freq="D", name="date")
    empty = pd.DataFrame({k: np.nan for k in config.keys}, index=idx)
    m = config.metrics[0]
    charts.trend_chart(empty, m, charts.LIGHT, 0)
    charts.calendar_chart(empty[m.key], m, charts.LIGHT)
    charts.weekday_chart(empty[m.key], m, charts.LIGHT, 0)
    charts.pair_chart(
        analytics.pair_counts(empty, config.keys[0], config.keys[1]),
        m,
        config.metrics[1],
        charts.LIGHT,
    )


def test_categorical_colours_do_not_cycle():
    with pytest.raises(IndexError):
        charts.LIGHT.color(8)


def test_ink_on_picks_readable_text():
    assert charts._ink_on("#0d366b") == "#ffffff"
    assert charts._ink_on("#cde2fb") == "#0b0b0b"


def test_theme_for():
    assert charts.theme_for("dark") is charts.DARK
    assert charts.theme_for("light") is charts.LIGHT
    assert charts.theme_for(None) is charts.LIGHT


def test_trend_window_sets_the_average_and_its_label(daily, config):
    m = config.metrics[0]
    fig = charts.trend_chart(daily, m, charts.LIGHT, 0, days=60, window=14)
    avg = next(t for t in fig.data if t.name == "14-day avg")
    expected = analytics.last_days(analytics.rolling_mean(daily[m.key], 14), 60)
    np.testing.assert_allclose(np.asarray(avg.y, dtype=float), expected.to_numpy(), equal_nan=True)


def test_trend_window_one_draws_the_daily_values_only(daily, config):
    m = config.metrics[0]
    fig = charts.trend_chart(daily, m, charts.LIGHT, 0, days=60, window=1)
    assert [t.name for t in fig.data if t.name] == ["Daily"]


def test_overlay_uses_the_window(daily, config):
    key = config.metrics[0].key
    fig = charts.overlay_chart(daily, config.metrics[:1], config.metrics, charts.LIGHT, window=21)
    expected = analytics.rolling_mean(daily[key], 21)
    np.testing.assert_allclose(
        np.asarray(fig.data[0].y, dtype=float), expected.to_numpy(), equal_nan=True
    )


def test_weekday_jitter_is_stable_across_ranges(daily, config):
    """A day's dot must not move when the visible range changes."""
    m = config.metrics[0]
    full = charts.weekday_chart(daily[m.key], m, charts.LIGHT, 0).data[0]
    tail = charts.weekday_chart(daily[m.key].iloc[-60:], m, charts.LIGHT, 0).data[0]
    by_date = dict(zip(full.customdata, full.x, strict=True))
    for label, x in zip(tail.customdata, tail.x, strict=True):
        assert by_date[label] == pytest.approx(x)


# ----------------------------------------------------------------------------- weather


def _response(metrics, mean=0.8, z=3.0):
    rows = []
    for m in metrics:
        for b in charts.WEATHER_BINS:
            big = b == "Big drop"
            rows.append({"metric": m.key, "bin": b, "mean": mean if big else 0.05, "se": 0.2,
                         "n": 40, "z": z if big else 0.2})  # fmt: skip
    return pd.DataFrame(rows)


@pytest.mark.parametrize("theme", [charts.LIGHT, charts.DARK])
def test_weather_response_flips_colour_for_higher_is_better(config, theme):
    fig = charts.weather_response_chart(_response(config.metrics), config.metrics, theme)
    z = np.asarray(fig.data[1].z)
    rows = {m.key: i for i, m in enumerate(config.metrics)}
    assert z[rows["headache"], 0] > 0  # rating up, lower is better -> worse (red side)
    assert z[rows["excitement"], 0] < 0  # rating up, higher is better -> better (blue side)
    assert (fig.data[1].zmin, fig.data[1].zmax) == (-1.0, 1.0)
    texts = [a.text for a in fig.layout.annotations]
    assert texts == ["+0.8"] * len(config.metrics)  # only the clear cells are labelled


def test_weather_response_handles_a_metric_with_too_few_days(config):
    resp = _response(config.metrics)
    resp.loc[resp["metric"] == "neck_pain", ["mean", "se", "z"]] = np.nan
    fig = charts.weather_response_chart(resp, config.metrics, charts.LIGHT)
    assert np.isnan(np.asarray(fig.data[1].z, dtype=float)[-1]).all()
    assert "too few days" in fig.data[0].customdata[-1][0]


def _profile(peak=1.0, events=8):
    idx = pd.Index(range(-2, 4), name="offset")
    mean = np.where(idx == 1, peak, 0.1)
    prof = pd.DataFrame({"mean": mean, "ci_low": mean - 0.4, "ci_high": mean + 0.4, "n": 8},
                        index=idx)  # fmt: skip
    prof.attrs["events"] = events
    return prof


@pytest.mark.parametrize("theme", [charts.LIGHT, charts.DARK])
def test_event_profile_chart(config, theme):
    m = config.metrics[0]
    empty = _profile() * np.nan
    fig = charts.event_profile_chart(_profile(), empty, m, theme, 0)
    assert [t.name for t in fig.data] == ["After big drops (8)"]  # an empty profile is left out
    assert fig.data[0].line.color == theme.color(0)
    fig2 = charts.event_profile_chart(_profile(), _profile(-0.5), m, theme, 0)
    assert [t.line.dash for t in fig2.data] == ["solid", "dash"]


@pytest.mark.parametrize("theme", [charts.LIGHT, charts.DARK])
def test_weather_timeline_marks_big_days_and_keeps_gaps(config, theme):
    idx = pd.date_range("2026-01-01", periods=30, freq="D", name="date")
    ratings = pd.Series(np.arange(30) % 10, index=idx, dtype=float)
    ratings.iloc[5] = np.nan
    change = pd.Series(np.linspace(-6, 6, 30), index=idx)
    fig = charts.weather_timeline_chart(
        ratings, change, config.metrics[0], theme, 0, change_label="Pressure, 24 h change",
        unit="hPa", drop_below=-4, rise_above=4, days=None,
    )  # fmt: skip
    assert np.isnan(fig.data[0].y[5])  # missing stays missing
    colors = list(fig.data[1].marker.color)
    assert colors[0] == theme.muted and colors[15] == theme.baseline
    assert fig.layout.yaxis2.tickvals is None and fig.data[1].yaxis == "y2"
