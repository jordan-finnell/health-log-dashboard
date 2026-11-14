"""Synthetic health-log generator for demo mode, tests and screenshots.

Output mimics the *raw* sheet export (header names, unpadded Google Forms timestamps,
duplicate and missing days, a late-starting metric) so the full transform pipeline is
exercised. It is generated from a small invented model and is NOT derived from any real
data.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date

import numpy as np
import pandas as pd

from .config import MetricsConfig


def generate_raw(
    config: MetricsConfig,
    *,
    days: int = 180,
    end: date | None = None,
    seed: int = 0,
    miss_rate: float = 0.06,
    double_rate: float = 0.05,
    late_start: Mapping[str, float] | None = None,
    weather_change: pd.Series | None = None,
) -> pd.DataFrame:
    """Return a raw, sheet-shaped DataFrame covering ``days`` days ending on ``end``.

    ``late_start`` maps metric key -> fraction of the log before which it is blank,
    mimicking a question added to the survey part-way through. By default that is the
    last metric in the config, blank for the first half.

    ``weather_change`` (a daily pressure change, hPa, indexed by date) makes some metrics
    worse the day after a pressure drop, each to its own invented degree, so the demo's
    Weather page has a pattern to find. Its random draws come from a separate stream, so
    leaving it out gives exactly the same log as before.
    """
    if days < 1:
        raise ValueError("days must be >= 1")
    if late_start is None:  # by default the last metric is a late survey addition
        late_start = {config.metrics[-1].key: 0.5}
    rng = np.random.default_rng(seed)
    end_ts = pd.Timestamp(end or date.today()).normalize()
    dates = pd.date_range(end=end_ts, periods=days, freq="D")

    burden = _latent_burden(rng, days)
    weekly = 0.4 * np.sin(2 * np.pi * (dates.day_of_week.to_numpy() - 1) / 7)
    weather = _weather_effect(config, dates, weather_change, seed)

    columns: dict[str, np.ndarray] = {}
    for metric in config.metrics:
        span = metric.max - metric.min
        sign = -1.0 if metric.higher_is_better else 1.0
        base_frac = rng.uniform(0.55, 0.7) if metric.higher_is_better else rng.uniform(0.2, 0.4)
        loading = rng.uniform(0.8, 1.3)
        noise = rng.normal(0, 0.7, size=days)
        # Each metric also drifts on its own, so they can diverge instead of all moving together.
        drift = _ar1(rng, days, phi=0.9, sd=0.25)
        values = metric.min + span * base_frac + sign * (loading * burden + weekly) + drift + noise
        values = values + sign * weather.get(metric.key, 0.0)
        values = np.clip(np.rint(values), metric.min, metric.max) + 0.0  # +0.0 normalises -0.0
        frac = late_start.get(metric.key, 0.0)
        values[: int(frac * days)] = np.nan
        columns[metric.column] = values

    rows = []
    first_kept = True
    for i, day in enumerate(dates):
        if rng.random() < miss_rate:
            continue
        submissions = 2 if rng.random() < double_rate else 1
        for n in range(submissions):
            values = {col: vals[i] for col, vals in columns.items()}
            if n == 1:  # a second, slightly different submission later the same day
                values = {c: _jitter(v, rng) for c, v in values.items()}
            # Evening log (18-23h); the occasional second one lands after midnight (0-7h the next
            # calendar day), which to_daily's rollover assigns back to the same day.
            stamp = day + pd.Timedelta(
                hours=int(rng.integers(8 + 6 * n, 14 + 8 * n)) + 10,
                minutes=int(rng.integers(0, 60)),
                seconds=int(rng.integers(0, 60)),
            )
            ts = _fmt_date(stamp) if first_kept else _fmt_datetime(stamp)
            first_kept = False
            rows.append({config.timestamp_column: ts, **values})

    return pd.DataFrame(rows, columns=[config.timestamp_column, *columns])


def _weather_effect(
    config: MetricsConfig,
    dates: pd.DatetimeIndex,
    weather_change: pd.Series | None,
    seed: int,
) -> dict[str, np.ndarray]:
    """Per-metric "worse by" amounts the day after pressure falls (empty without weather)."""
    if weather_change is None:
        return {}
    rng = np.random.default_rng([seed, 1])  # separate stream: the base log is unchanged
    prior = weather_change.shift(1, freq="D").reindex(dates).to_numpy(dtype="float64")
    # Only falls beyond ~2 hPa matter, growing with their size.
    fall = np.nan_to_num(np.clip(-prior - 2.0, 0.0, None) / 2.5)
    effects = {}
    for metric in config.metrics:
        sensitive = rng.random() < 0.7
        strength = rng.uniform(0.6, 1.3)
        if sensitive:
            effects[metric.key] = strength * fall
    return effects


def _ar1(rng: np.random.Generator, n: int, *, phi: float, sd: float) -> np.ndarray:
    """A slowly wandering zero-mean series."""
    out = np.empty(n)
    x = 0.0
    for i in range(n):
        x = phi * x + rng.normal(0, sd)
        out[i] = x
    return out


def _latent_burden(rng: np.random.Generator, n: int) -> np.ndarray:
    """AR(1) drift plus occasional multi-day flare-ups, shared by all metrics."""
    out = np.empty(n)
    x = 0.0
    flare_left = 0
    flare_amp = 0.0
    for i in range(n):
        if flare_left == 0 and rng.random() < 0.025:
            flare_left = int(rng.integers(3, 9))
            flare_amp = float(rng.uniform(1.5, 3.0))
        x = 0.8 * x + rng.normal(0, 0.4)
        boost = flare_amp if flare_left > 0 else 0.0
        flare_left = max(0, flare_left - 1)
        out[i] = x + boost
    return out


def _jitter(value: float, rng: np.random.Generator) -> float:
    return value if np.isnan(value) else value + float(rng.integers(-1, 2))


def _fmt_date(ts: pd.Timestamp) -> str:
    return f"{ts.month}/{ts.day}/{ts.year}"


def _fmt_datetime(ts: pd.Timestamp) -> str:
    return f"{_fmt_date(ts)} {ts.hour}:{ts.minute:02d}:{ts.second:02d}"
