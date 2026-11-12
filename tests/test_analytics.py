import math

import numpy as np
import pandas as pd
import pytest

from health_log_dashboard import analytics


def series(values, start="2026-03-01"):
    idx = pd.date_range(start, periods=len(values), freq="D", name="date")
    return pd.Series(values, index=idx, dtype="float64")


def frame(values_by_col, start="2026-03-01"):
    n = len(next(iter(values_by_col.values())))
    idx = pd.date_range(start, periods=n, freq="D", name="date")
    return pd.DataFrame(values_by_col, index=idx, dtype="float64")


class TestRollingMean:
    def test_basic(self):
        out = analytics.rolling_mean(series([1, 2, 3, 4, 5, 6, 7, 8]), window=4, min_periods=4)
        assert math.isnan(out.iloc[2])
        assert out.iloc[3] == pytest.approx(2.5)
        assert out.iloc[7] == pytest.approx(6.5)

    def test_tolerates_gaps_when_enough_data(self):
        s = series([2, np.nan, 4, np.nan, 6, 8, 10])
        out = analytics.rolling_mean(s, window=4)  # default min_periods = 2
        assert out.iloc[-1] == pytest.approx((6 + 8 + 10) / 3)

    def test_nan_when_too_sparse(self):
        s = series([np.nan, np.nan, np.nan, 5.0])
        assert math.isnan(analytics.rolling_mean(s, window=4).iloc[-1])

    def test_invalid_window(self):
        with pytest.raises(ValueError):
            analytics.rolling_mean(series([1, 2]), window=0)


class TestPeriodComparison:
    def test_delta(self):
        s = series([1] * 7 + [3] * 7)
        cmp = analytics.period_comparison(s, days=7)
        assert cmp.current == 3
        assert cmp.previous == 1
        assert cmp.delta == 2
        assert (cmp.current_n, cmp.previous_n) == (7, 7)

    def test_ignores_missing_in_means_and_counts_them(self):
        s = series([1, 1, 1, 1, 1, 1, np.nan, 4, np.nan, 4, 4, 4, 4, 4])
        cmp = analytics.period_comparison(s, days=7)
        assert cmp.current == 4
        assert cmp.current_n == 6
        assert cmp.previous_n == 6

    def test_no_previous_period_gives_nan_delta(self):
        cmp = analytics.period_comparison(series([2, 2, 2]), days=7)
        assert cmp.current == 2
        assert math.isnan(cmp.previous)
        assert math.isnan(cmp.delta)

    def test_all_missing(self):
        cmp = analytics.period_comparison(series([np.nan] * 14), days=7)
        assert math.isnan(cmp.current) and math.isnan(cmp.delta)


class TestLatest:
    def test_returns_last_non_missing(self):
        d, v = analytics.latest(series([1, 2, np.nan, np.nan]))
        assert d == pd.Timestamp("2026-03-02")
        assert v == 2

    def test_none_when_empty(self):
        assert analytics.latest(series([np.nan, np.nan])) is None


class TestAggregate:
    def test_weekly_mean(self):
        df = frame({"a": list(range(14))}, start="2026-03-02")  # Monday
        weekly = analytics.aggregate(df, "W")
        assert weekly["a"].tolist() == [pytest.approx(3.0), pytest.approx(10.0)]


class TestCorrelation:
    def test_perfect_positive_and_negative(self):
        x = np.arange(30, dtype=float)
        df = frame({"a": x, "b": x * 2, "c": -x})
        corr = analytics.correlation_matrix(df, min_periods=10)
        assert corr.loc["a", "b"] == pytest.approx(1.0)
        assert corr.loc["a", "c"] == pytest.approx(-1.0)

    def test_nan_when_too_few_overlapping_days(self):
        x = np.arange(30, dtype=float)
        late = np.where(np.arange(30) < 25, np.nan, x)
        corr = analytics.correlation_matrix(frame({"a": x, "b": late}), min_periods=14)
        assert math.isnan(corr.loc["a", "b"])


class TestWeekdaySummary:
    def test_orders_mon_to_sun_with_distribution(self):
        # 2026-03-02 is a Monday; two weeks, so each weekday has two values (w, w + 10)
        values = [w + 10 * week for week in range(2) for w in range(7)]
        out = analytics.weekday_summary(frame({"a": values}, start="2026-03-02")["a"])
        assert list(out.index) == analytics.WEEKDAYS
        assert out["n"].tolist() == [2] * 7
        assert out["mean"].tolist() == [w + 5 for w in range(7)]
        assert out.loc["Mon", ["min", "max", "median"]].tolist() == [0, 10, 5]
        assert out.loc["Mon", ["q25", "q75"]].tolist() == [2.5, 7.5]

    def test_missing_weekday_has_zero_n_and_nan_stats(self):
        out = analytics.weekday_summary(frame({"a": [1.0, 2.0]}, start="2026-03-02")["a"])
        assert out.loc["Sun", "n"] == 0
        assert math.isnan(out.loc["Sun", "mean"])
        assert out.loc["Tue", "n"] == 1

    def test_nan_days_are_ignored(self):
        series = frame({"a": [4.0, np.nan] + [np.nan] * 5 + [6.0]}, start="2026-03-02")["a"]
        out = analytics.weekday_summary(series)
        assert out.loc["Mon", "n"] == 2 and out.loc["Mon", "mean"] == 5


class TestStreak:
    def test_current_and_longest(self):
        # logged: 3 days, gap, 2 days  -> current 2, longest 3
        df = frame({"a": [1, 1, 1, np.nan, 1, 1]})
        s = analytics.logging_streak(df)
        assert (s.current, s.longest) == (2, 3)

    def test_row_counts_as_logged_if_any_metric_present(self):
        df = frame({"a": [1, np.nan, np.nan], "b": [np.nan, 2, 3]})
        assert analytics.logging_streak(df).current == 3

    def test_grace_period_for_today_not_yet_logged(self):
        df = frame({"a": [1, 1, 1]})  # last entry 2026-03-03
        s = analytics.logging_streak(df, as_of="2026-03-04")
        assert s.current == 3

    def test_gap_longer_than_grace_resets_to_zero(self):
        df = frame({"a": [1, 1, 1]})
        s = analytics.logging_streak(df, as_of="2026-03-06")
        assert s.current == 0
        assert s.longest == 3

    def test_empty(self):
        s = analytics.logging_streak(frame({"a": []}))
        assert (s.current, s.longest) == (0, 0)


class TestCompletionRate:
    def test_whole_log_and_window(self):
        df = frame({"a": [1, np.nan, 1, np.nan, 1, 1, 1, 1]})
        assert analytics.completion_rate(df) == pytest.approx(6 / 8)
        assert analytics.completion_rate(df, days=4) == 1.0

    def test_empty_is_nan(self):
        assert math.isnan(analytics.completion_rate(frame({"a": []})))
