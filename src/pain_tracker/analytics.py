"""Pure-pandas analytics over the daily frame produced by ``transform.to_daily``."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def rolling_mean(series: pd.Series, window: int, min_periods: int | None = None) -> pd.Series:
    """Trailing mean over ``window`` calendar days, tolerant of missed days.

    By default at least half the window must have data, otherwise the result is NaN.
    """
    if window < 1:
        raise ValueError("window must be >= 1")
    if min_periods is None:
        min_periods = max(1, math.ceil(window / 2))
    return series.rolling(window, min_periods=min_periods).mean()


@dataclass(frozen=True)
class PeriodComparison:
    current: float
    previous: float
    delta: float
    current_n: int
    previous_n: int


def period_comparison(series: pd.Series, days: int = 7) -> PeriodComparison:
    """Mean of the last ``days`` days vs. the ``days`` before that.

    Assumes a continuous daily index (as produced by ``to_daily``). ``delta`` is
    ``current - previous`` and is NaN if either period has no data.
    """
    if days < 1:
        raise ValueError("days must be >= 1")
    current = series.iloc[-days:]
    previous = series.iloc[-2 * days : -days]
    cur_mean = current.mean() if current.notna().any() else math.nan
    prev_mean = previous.mean() if previous.notna().any() else math.nan
    return PeriodComparison(
        current=float(cur_mean),
        previous=float(prev_mean),
        delta=float(cur_mean - prev_mean),
        current_n=int(current.notna().sum()),
        previous_n=int(previous.notna().sum()),
    )


def latest(series: pd.Series) -> tuple[pd.Timestamp, float] | None:
    """Most recent non-missing (date, value), or None if the series is empty."""
    valid = series.dropna()
    if valid.empty:
        return None
    return valid.index[-1], float(valid.iloc[-1])


def aggregate(df: pd.DataFrame, freq: str = "W") -> pd.DataFrame:
    """Mean per period. ``freq`` is a pandas offset alias, e.g. ``"W"`` (week) or ``"MS"``."""
    return df.resample(freq).mean()


def correlation_matrix(
    df: pd.DataFrame, method: str = "spearman", min_periods: int = 14
) -> pd.DataFrame:
    """Pairwise correlation of metrics (Spearman by default: ratings are ordinal)."""
    return df.corr(method=method, min_periods=min_periods)


def day_of_week_profile(df: pd.DataFrame) -> pd.DataFrame:
    """Mean of each metric by weekday, rows ordered Mon..Sun."""
    by_day = df.groupby(df.index.day_of_week).mean().reindex(range(7))
    by_day.index = pd.Index(WEEKDAYS, name="weekday")
    return by_day


@dataclass(frozen=True)
class Streak:
    current: int
    longest: int


def logged_days(df: pd.DataFrame) -> pd.Series:
    """Boolean per day: was anything recorded?"""
    return df.notna().any(axis=1)


def logging_streak(df: pd.DataFrame, as_of: date | pd.Timestamp | None = None) -> Streak:
    """Consecutive days logged, ending at ``as_of`` (default: the last row).

    If ``as_of`` has no entry yet the streak is not broken: it is counted through the
    previous day (a grace period for "haven't filled it in yet today"). A longer gap gives 0.
    """
    logged = logged_days(df)
    if logged.empty:
        return Streak(current=0, longest=0)

    end = pd.Timestamp(as_of).normalize() if as_of is not None else logged.index[-1]
    full = logged.reindex(pd.date_range(logged.index[0], max(end, logged.index[-1]), freq="D"))
    full = full.fillna(False).astype(bool)

    longest = _longest_run(full.to_numpy())

    if end not in full.index:
        return Streak(current=0, longest=longest)
    tail = full.loc[:end]
    if not tail.iloc[-1]:
        tail = tail.iloc[:-1]  # grace: today not logged yet
    current = _trailing_run(tail.to_numpy())
    return Streak(current=current, longest=longest)


def completion_rate(df: pd.DataFrame, days: int | None = None) -> float:
    """Fraction of days with an entry, over the last ``days`` days (default: whole log)."""
    logged = logged_days(df)
    if days is not None:
        logged = logged.iloc[-days:]
    return float(logged.mean()) if len(logged) else math.nan


def _longest_run(flags: np.ndarray) -> int:
    best = run = 0
    for flag in flags:
        run = run + 1 if flag else 0
        best = max(best, run)
    return best


def _trailing_run(flags: np.ndarray) -> int:
    run = 0
    for flag in flags[::-1]:
        if not flag:
            break
        run += 1
    return run
