import numpy as np
import pandas as pd
import pytest

from health_log_dashboard.config import ConfigError
from health_log_dashboard.transform import to_daily


def raw_frame(rows):
    """Build a raw frame with the example config's headers from compact tuples.

    Each row: (timestamp, headache, fatigue, depression, anxiety, excitement, neck_pain)
    """
    cols = [
        "Timestamp",
        "Headache Severity",
        "Fatigue / Body Aches",
        "Depression",
        "Anxiety",
        "Excitement",
        "Neck Pain",
    ]
    return pd.DataFrame(rows, columns=cols)


def test_parses_mixed_timestamp_formats(config):
    raw = raw_frame(
        [
            ("3/9/2026", 1, 1, 1, 1, 5, 1),  # date-only
            ("3/10/2026 18:05:09", 2, 2, 2, 2, 5, 2),  # unpadded, single-digit hour
            ("3/11/2026 14:30:00", 3, 3, 3, 3, 5, 3),
        ]
    )
    daily = to_daily(raw, config)
    assert list(daily.index) == list(pd.date_range("2026-03-09", "2026-03-11"))
    assert daily["headache"].tolist() == [1, 2, 3]


def test_index_is_named_date_and_daily_frequency(config):
    raw = raw_frame(
        [("3/1/2026 15:00:00", 1, 1, 1, 1, 1, 1), ("3/3/2026 15:00:00", 2, 2, 2, 2, 2, 2)]
    )
    daily = to_daily(raw, config)
    assert daily.index.name == "date"
    assert len(daily) == 3  # includes the missing 3/2


def test_missing_days_are_nan_not_interpolated(config):
    raw = raw_frame(
        [("3/1/2026 15:00:00", 4, 4, 4, 4, 4, 4), ("3/4/2026 15:00:00", 8, 8, 8, 8, 8, 8)]
    )
    daily = to_daily(raw, config)
    assert daily.loc["2026-03-02":"2026-03-03"].isna().all().all()


def test_same_day_keeps_latest_whole_row(config):
    raw = raw_frame(
        [
            ("3/1/2026 13:00:00", 2, 2, 2, 2, 2, 7),
            ("3/1/2026 20:00:00", 5, 5, 5, 5, 5, np.nan),  # later, neck pain blank
        ]
    )
    daily = to_daily(raw, config)
    assert len(daily) == 1
    assert daily["headache"].iloc[0] == 5
    # Blank in the later submission must NOT be back-filled from the earlier one.
    assert np.isnan(daily["neck_pain"].iloc[0])


def test_same_day_ordering_does_not_depend_on_row_order(config):
    raw = raw_frame(
        [
            ("3/1/2026 20:00:00", 5, 5, 5, 5, 5, 5),
            ("3/1/2026 13:00:00", 2, 2, 2, 2, 2, 2),
        ]
    )
    assert to_daily(raw, config)["headache"].iloc[0] == 5


def test_blank_strings_become_nan_never_zero(config):
    raw = raw_frame([("3/1/2026 15:00:00", "3", "", "4", " ", "5", "")])
    daily = to_daily(raw, config)
    row = daily.iloc[0]
    assert row["headache"] == 3
    assert np.isnan(row["fatigue"])
    assert np.isnan(row["anxiety"])
    assert np.isnan(row["neck_pain"])


def test_out_of_range_values_become_nan(config):
    raw = raw_frame([("3/1/2026 15:00:00", 11, -1, 10, 0, 5, 3)])
    row = to_daily(raw, config).iloc[0]
    assert np.isnan(row["headache"])  # above max
    assert np.isnan(row["fatigue"])  # below min
    assert row["depression"] == 10  # boundary is valid
    assert row["anxiety"] == 0  # boundary is valid, and 0 is a real value


def test_unparseable_timestamps_are_dropped(config):
    raw = raw_frame([("not a date", 1, 1, 1, 1, 1, 1), ("3/1/2026 15:00:00", 2, 2, 2, 2, 2, 2)])
    daily = to_daily(raw, config)
    assert len(daily) == 1
    assert daily["headache"].iloc[0] == 2


def test_unsorted_input_is_sorted(config):
    raw = raw_frame(
        [("3/3/2026 15:00:00", 3, 3, 3, 3, 3, 3), ("3/1/2026 15:00:00", 1, 1, 1, 1, 1, 1)]
    )
    daily = to_daily(raw, config)
    assert daily.index.is_monotonic_increasing
    assert daily["headache"].iloc[0] == 1


def test_header_whitespace_is_tolerated(config):
    raw = raw_frame([("3/1/2026 15:00:00", 1, 1, 1, 1, 1, 1)])
    raw.columns = [f" {c} " for c in raw.columns]
    assert len(to_daily(raw, config)) == 1


def test_missing_column_raises_clear_error(config):
    raw = raw_frame([("3/1/2026 15:00:00", 1, 1, 1, 1, 1, 1)]).drop(columns="Anxiety")
    with pytest.raises(ConfigError, match="Anxiety"):
        to_daily(raw, config)


def test_empty_or_all_invalid_input_returns_empty_frame_with_columns(config):
    raw = raw_frame([("garbage", 1, 1, 1, 1, 1, 1)])
    daily = to_daily(raw, config)
    assert daily.empty
    assert list(daily.columns) == config.keys
    assert daily.index.name == "date"


def test_log_before_noon_counts_for_the_previous_day(config):
    raw = raw_frame(
        [
            ("3/1/2026 20:00:00", 4, 4, 4, 4, 4, 4),
            ("3/2/2026 0:30:00", 6, 6, 6, 6, 6, 6),  # logged after midnight, about 3/1
        ]
    )
    daily = to_daily(raw, config)
    assert list(daily.index) == [pd.Timestamp("2026-03-01")]  # nothing lands on 3/2
    assert daily["headache"].iloc[0] == 6  # the later submission wins


def test_after_midnight_log_fills_the_day_instead_of_leaving_a_gap(config):
    raw = raw_frame(
        [
            ("3/1/2026 21:00:00", 1, 1, 1, 1, 1, 1),
            ("3/3/2026 0:45:00", 3, 3, 3, 3, 3, 3),  # really 3/2
            ("3/3/2026 22:00:00", 4, 4, 4, 4, 4, 4),
        ]
    )
    daily = to_daily(raw, config)
    assert list(daily.index) == list(pd.date_range("2026-03-01", "2026-03-03"))
    assert daily["headache"].tolist() == [1, 3, 4]


def test_rollover_boundary_noon_is_the_new_day(config):
    raw = raw_frame(
        [
            ("3/2/2026 11:59:59", 1, 1, 1, 1, 1, 1),  # still 3/1
            ("3/2/2026 12:00:00", 2, 2, 2, 2, 2, 2),  # 3/2
        ]
    )
    daily = to_daily(raw, config)
    assert list(daily.index) == [pd.Timestamp("2026-03-01"), pd.Timestamp("2026-03-02")]
    assert daily["headache"].tolist() == [1, 2]


def test_date_only_rows_are_not_shifted(config):
    raw = raw_frame([("3/1/2026", 1, 1, 1, 1, 1, 1), ("3/2/2026 18:00:00", 2, 2, 2, 2, 2, 2)])
    daily = to_daily(raw, config)
    assert list(daily.index) == list(pd.date_range("2026-03-01", "2026-03-02"))


def test_rollover_hour_zero_disables_the_shift(config):
    raw = raw_frame([("3/2/2026 0:30:00", 1, 1, 1, 1, 1, 1)])
    assert list(to_daily(raw, config, rollover_hour=0).index) == [pd.Timestamp("2026-03-02")]
