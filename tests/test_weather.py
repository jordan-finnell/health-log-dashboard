"""The app's weather glue: location from secrets, and demo never touching it."""

import pytest
from winds_of_change import OpenMeteoSource

from health_log_dashboard.config import ConfigError, Mode, resolve_mode
from health_log_dashboard.sources import DEMO_WEATHER
from health_log_dashboard.weather import build_weather_source, higher_is_better, weather_location

WEATHER = {"latitude": 51.48, "longitude": -0.01}
FULL = {
    "gcp_service_account": {"type": "service_account"},
    "sheet_id": "x",
    "worksheet": "Sheet1",
}


def test_location_is_optional_and_rounded():
    assert weather_location(None) is None
    assert weather_location(FULL) is None
    loc = weather_location({**FULL, "weather": WEATHER})
    assert (loc.latitude, loc.longitude) == (51.5, -0.0)


@pytest.mark.parametrize(
    "settings",
    [{"latitude": "51.48", "longitude": -0.01}, {"latitude": 51.48}, {"lat": 1, "longitude": 1}],
)
def test_bad_weather_settings_are_config_errors_without_values(settings):
    with pytest.raises(ConfigError, match=r"\[weather\]") as info:
        weather_location({"weather": settings})
    assert "51.48" not in str(info.value)


def test_demo_always_uses_synthetic_weather_and_ignores_secrets():
    assert build_weather_source(Mode.DEMO, {**FULL, "weather": WEATHER}) is DEMO_WEATHER
    assert build_weather_source(Mode.DEMO, {"weather": {"latitude": "broken"}}) is DEMO_WEATHER


def test_live_uses_open_meteo_only_when_configured():
    assert build_weather_source(Mode.LIVE, FULL) is None
    source = build_weather_source(Mode.LIVE, {**FULL, "weather": WEATHER})
    assert isinstance(source, OpenMeteoSource) and source.location.latitude == 51.5


def test_weather_settings_do_not_change_the_mode():
    assert resolve_mode({"weather": WEATHER}, {}) is Mode.DEMO
    assert resolve_mode({**FULL, "weather": WEATHER}, {}) is Mode.LIVE


def test_higher_is_better_map(config):
    flags = higher_is_better(config)
    assert set(flags) == set(config.keys) and flags["excitement"] is True


def test_forecast_source_is_live_only():
    from winds_of_change import OpenMeteoForecastSource

    from health_log_dashboard.weather import build_forecast_source

    assert build_forecast_source(Mode.DEMO, {**FULL, "weather": WEATHER}) is None
    assert build_forecast_source(Mode.LIVE, FULL) is None
    assert isinstance(
        build_forecast_source(Mode.LIVE, {**FULL, "weather": WEATHER}), OpenMeteoForecastSource
    )
