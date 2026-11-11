import numpy as np
import pandas as pd
import pytest

from health_log_dashboard import analytics


def series(values, start="2026-03-02"):  # 2026-03-02 is a Monday
    idx = pd.date_range(start, periods=len(values), freq="D", name="date")
    return pd.Series(values, index=idx, dtype="float64")


class TestLastDays:
    def test_trailing_window(self):
        s = series(range(10))
        assert analytics.last_days(s, 3).tolist() == [7, 8, 9]

    def test_none_returns_everything(self):
        s = series(range(5))
        assert analytics.last_days(s, None) is s

    def test_window_larger_than_data(self):
        assert len(analytics.last_days(series(range(4)), 30)) == 4

    def test_works_on_frames_and_rejects_bad_days(self):
        df = pd.DataFrame({"a": series(range(6))})
        assert len(analytics.last_days(df, 2)) == 2
        with pytest.raises(ValueError):
            analytics.last_days(df, 0)

    def test_empty(self):
        assert analytics.last_days(series([]), 7).empty


class TestCalendarGrid:
    def test_full_weeks(self):
        values, in_range = analytics.calendar_grid(series(range(14)))  # Mon..Sun x 2
        assert values.shape == (2, 7)
        assert list(values.columns) == analytics.WEEKDAYS
        assert values.iloc[0].tolist() == [0, 1, 2, 3, 4, 5, 6]
        assert values.iloc[1].tolist() == [7, 8, 9, 10, 11, 12, 13]
        assert in_range.to_numpy().all()

    def test_partial_weeks_are_padded_and_flagged(self):
        # Starts Wednesday 2026-03-04, 5 days -> ends Sunday; first week begins Monday 03-02
        values, in_range = analytics.calendar_grid(series([1, 2, 3, 4, 5], start="2026-03-04"))
        assert values.index[0] == pd.Timestamp("2026-03-02")
        assert np.isnan(values.iloc[0, 0]) and np.isnan(values.iloc[0, 1])  # Mon, Tue before log
        assert not in_range.iloc[0, 0] and not in_range.iloc[0, 1]
        assert in_range.iloc[0, 2]
        assert values.iloc[0, 2] == 1

    def test_missing_day_is_nan_but_in_range(self):
        values, in_range = analytics.calendar_grid(series([1, np.nan, 3]))
        assert np.isnan(values.iloc[0, 1])
        assert in_range.iloc[0, 1]

    def test_empty(self):
        values, in_range = analytics.calendar_grid(series([]))
        assert values.empty and in_range.empty


class TestPairCounts:
    def test_counts_only_days_with_both(self):
        df = pd.DataFrame(
            {"a": [1, 1, 2, np.nan, 3], "b": [5, 5, 5, 5, np.nan]},
            index=pd.date_range("2026-03-01", periods=5),
        )
        counts = analytics.pair_counts(df, "a", "b")
        assert counts.shape == (11, 11)
        assert counts.loc[1, 5] == 2
        assert counts.loc[2, 5] == 1
        assert counts.to_numpy().sum() == 3  # the NaN rows are excluded

    def test_float_ratings_are_rounded(self):
        df = pd.DataFrame(
            {"a": [2.0, 2.0], "b": [7.0, 7.0]}, index=pd.date_range("2026-03-01", periods=2)
        )
        assert analytics.pair_counts(df, "a", "b").loc[2, 7] == 2

    def test_no_data_is_all_zero(self):
        df = pd.DataFrame(
            {"a": [np.nan], "b": [np.nan]}, index=pd.date_range("2026-03-01", periods=1)
        )
        assert analytics.pair_counts(df, "a", "b").to_numpy().sum() == 0
