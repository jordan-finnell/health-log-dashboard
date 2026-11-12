"""Turn a raw sheet export into a clean, one-row-per-calendar-day DataFrame."""

from __future__ import annotations

import pandas as pd

from .config import ConfigError, MetricsConfig

DATE_INDEX_NAME = "date"

# A submission made before this hour belongs to the previous day: the author sometimes logs
# shortly after midnight for the day that just ended. Noon itself counts as the new day.
DAY_ROLLOVER_HOUR = 12


def to_daily(
    raw: pd.DataFrame, config: MetricsConfig, rollover_hour: int = DAY_ROLLOVER_HOUR
) -> pd.DataFrame:
    """Clean raw form responses into a daily frame.

    - Column headers are mapped to the metric keys in ``config``.
    - Timestamps are parsed leniently (Google Forms ``M/D/YYYY H:MM:SS`` and date-only rows).
      Rows whose timestamp cannot be parsed are dropped.
    - Blank / non-numeric ratings and values outside a metric's scale become NaN. Missing is
      never treated as zero.
    - A submission is assigned to a day by shifting its timestamp back ``rollover_hour`` hours,
      so with the default (12) anything logged before noon counts for the previous day. Date-only
      rows carry no time of day and are never shifted. ``rollover_hour=0`` disables this.
    - If several submissions fall on one day, the latest *whole row* wins, so a blank in the
      later submission is not back-filled from an earlier one.
    - The result is reindexed to every calendar day between the first and last submission;
      days with no submission are all-NaN rows (nothing is interpolated).
    """
    raw = raw.rename(columns=lambda c: str(c).strip())

    needed = [config.timestamp_column, *(m.column for m in config.metrics)]
    missing = [c for c in needed if c not in raw.columns]
    if missing:
        raise ConfigError(f"sheet is missing expected column(s): {missing}")

    stamps = raw[config.timestamp_column].astype("string").str.strip()
    timestamps = pd.to_datetime(stamps, format="mixed", errors="coerce")

    # Date-only rows parse as 00:00, which the rollover would wrongly push to the day before.
    has_time = stamps.str.contains(":", na=False).astype(bool)
    shift = pd.Timedelta(hours=rollover_hour)

    df = pd.DataFrame({"timestamp": timestamps})
    df[DATE_INDEX_NAME] = (timestamps - shift * has_time.astype(int)).dt.normalize()
    for metric in config.metrics:
        values = pd.to_numeric(raw[metric.column], errors="coerce").astype("float64")
        df[metric.key] = values.where(values.between(metric.min, metric.max))

    df = df.dropna(subset=["timestamp"])
    if df.empty:
        return _empty_daily(config)

    df = df.sort_values("timestamp", kind="stable")
    df = df.drop_duplicates(subset=DATE_INDEX_NAME, keep="last")
    df = df.set_index(DATE_INDEX_NAME).drop(columns="timestamp")

    full_range = pd.date_range(df.index.min(), df.index.max(), freq="D", name=DATE_INDEX_NAME)
    return df.reindex(full_range)


def _empty_daily(config: MetricsConfig) -> pd.DataFrame:
    index = pd.DatetimeIndex([], name=DATE_INDEX_NAME)
    return pd.DataFrame({k: pd.Series(dtype="float64") for k in config.keys}, index=index)
