"""Glue between this app and the ``winds_of_change`` weather library.

Weather is optional. Live mode reads a ``[weather]`` table from secrets (latitude, longitude,
optional elevation and timezone). Demo mode always uses synthetic weather and never looks at
secrets, because a developer's real secrets file can be visible while running the demo.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from winds_of_change import (
    FACTORS,
    Location,
    LocationError,
    OpenMeteoForecastSource,
    OpenMeteoSource,
    Units,
    WeatherSource,
)

from .config import ConfigError, MetricsConfig, Mode
from .sources import DEMO_WEATHER

WEATHER_KEY = "weather"
DISPLAY_UNITS = Units(temperature="F")
WINDOWS: tuple[int, ...] = (3, 6, 12, 24, 48)
DEFAULT_WINDOW = 24
# Short names for the factor control; the library's labels are longer.
SHORT_LABELS = {"pressure": "Pressure", "dew_point": "Humidity", "temperature": "Temperature"}
FACTOR_KEYS = tuple(f.key for f in FACTORS)


def weather_location(secrets: Mapping[str, Any] | None) -> Location | None:
    """The configured location, or None when there is no ``[weather]`` table."""
    if not secrets or WEATHER_KEY not in secrets:
        return None
    settings = secrets[WEATHER_KEY]
    try:
        return Location.from_mapping(dict(settings) if isinstance(settings, Mapping) else settings)
    except LocationError as exc:
        raise ConfigError(f"[{WEATHER_KEY}] in secrets: {exc}") from None


def build_weather_source(mode: Mode, secrets: Mapping[str, Any] | None) -> WeatherSource | None:
    """Demo: synthetic weather (secrets ignored). Live: Open-Meteo, if a location is set."""
    if mode is Mode.DEMO:
        return DEMO_WEATHER
    location = weather_location(secrets)
    return OpenMeteoSource(location) if location is not None else None


def build_forecast_source(
    mode: Mode, secrets: Mapping[str, Any] | None
) -> OpenMeteoForecastSource | None:
    """Live only: the recent days plus the next ~2, for outlooks. Demo outlooks come from
    the synthetic series itself, which already runs past now."""
    if mode is Mode.DEMO:
        return None
    location = weather_location(secrets)
    return OpenMeteoForecastSource(location) if location is not None else None


def higher_is_better(config: MetricsConfig) -> dict[str, bool]:
    return {m.key: m.higher_is_better for m in config.metrics}
