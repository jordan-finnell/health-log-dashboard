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


def test_end_labels_only_for_four_or_fewer_series(daily, config):
    few = charts.overlay_chart(daily, config.metrics[:3], config.metrics, charts.LIGHT)
    many = charts.overlay_chart(daily, config.metrics, config.metrics, charts.LIGHT)
    assert len(few.layout.annotations) >= 1
    assert len(many.layout.annotations) == 0


def test_end_labels_use_text_ink_not_series_colour(daily, config):
    fig = charts.overlay_chart(daily, config.metrics[:2], config.metrics, charts.LIGHT)
    for ann in fig.layout.annotations:
        assert ann.font.color == charts.LIGHT.text_secondary


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
