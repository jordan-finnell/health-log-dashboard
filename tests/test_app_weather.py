"""The Weather page and the Home weather block, in demo and live mode, including failures."""

from datetime import date, timedelta
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest
from winds_of_change import WeatherError

import shared
from health_log_dashboard.sources import DEMO_WEATHER, SyntheticSource

APP_TIMEOUT = 120
APP = Path(__file__).resolve().parents[1] / "app"
WEATHER_PAGE = str(APP / "pages" / "4_Weather.py")
HOME = str(APP / "Home.py")
LIVE = {
    "sheet_id": "SHEET",
    "worksheet": "Form Responses 1",
    "gcp_service_account": {"type": "service_account"},
}


@pytest.fixture(autouse=True)
def fresh_caches():
    shared._load_daily.clear()
    shared._load_weather.clear()
    yield
    shared._load_daily.clear()
    shared._load_weather.clear()


def run(page, secrets=None):
    at = AppTest.from_file(page, default_timeout=APP_TIMEOUT)
    for key, value in (secrets or {}).items():
        at.secrets[key] = value
    return at.run()


def texts(at):
    return " ".join(
        str(e.value) for kind in (at.info, at.warning, at.error, at.markdown) for e in kind
    )


class FailingWeather:
    def load_hourly(self, start: date, end: date):
        raise WeatherError("could not reach the weather service")


@pytest.fixture
def live(monkeypatch):
    """Live mode whose sheet is synthetic (coupled to the demo weather)."""
    monkeypatch.delenv("DEMO_MODE", raising=False)

    def fake_build_source(mode, config, secrets=None):
        return SyntheticSource(config, weather=True)

    monkeypatch.setattr(shared, "build_source", fake_build_source)
    return monkeypatch


def test_demo_weather_page_renders_offline(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "1")  # conftest blocks the network
    at = run(WEATHER_PAGE)
    assert not at.exception, [e.value for e in at.exception]
    assert "synthetic weather" in " ".join(str(c.value) for c in at.caption)
    assert at.segmented_control(key="weather_factor").value == "pressure"
    for window in (3, 48):
        at.segmented_control(key="weather_window").set_value(window).run()
        assert not at.exception
    at.segmented_control(key="weather_lag").set_value(1).run()
    at.segmented_control(key="weather_factor").set_value("dew_point").run()
    assert not at.exception


def test_demo_home_shows_the_weather_block(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "1")
    at = run(HOME)
    assert not at.exception
    assert "Weather · next 24 h" in texts(at)


def test_live_with_weather_source(live):
    live.setattr(shared, "build_weather_source", lambda mode, secrets=None: DEMO_WEATHER)
    at = run(WEATHER_PAGE, LIVE)
    assert not at.exception, [e.value for e in at.exception]
    assert "Open-Meteo" in " ".join(str(c.value) for c in at.caption)


def test_live_without_weather_settings_explains_how_to_enable(live):
    at = run(WEATHER_PAGE, LIVE)
    assert not at.exception
    assert "Weather isn't set up" in texts(at)
    home = run(HOME, LIVE)
    assert not home.exception and "Weather · next" not in texts(home)


def test_live_with_malformed_weather_settings(live):
    at = run(WEATHER_PAGE, {**LIVE, "weather": {"latitude": "oops", "longitude": 0.0}})
    assert not at.exception
    assert "Weather settings problem" in texts(at)
    assert "oops" not in texts(at)


def test_live_fetch_failure_warns_and_home_still_renders(live):
    live.setattr(shared, "build_weather_source", lambda mode, secrets=None: FailingWeather())
    at = run(WEATHER_PAGE, LIVE)
    assert not at.exception
    assert "Couldn't load weather" in texts(at)
    home = run(HOME, LIVE)
    assert not home.exception
    assert len(home.metric) >= 6 and "Weather · next" not in texts(home)


class FakeForecast:
    """Recent days plus the next two, from the demo weather (no network)."""

    def __init__(self, fail=False):
        self.fail = fail

    def load_recent(self):
        if self.fail:
            raise WeatherError("could not reach the weather service")
        today = date.today()
        return DEMO_WEATHER.load_hourly(today - timedelta(days=31), today + timedelta(days=2))


def test_live_outlook_comes_from_the_forecast(live):
    live.setattr(shared, "build_weather_source", lambda mode, secrets=None: DEMO_WEATHER)
    live.setattr(shared, "build_forecast_source", lambda mode, secrets=None: FakeForecast())
    at = run(WEATHER_PAGE, LIVE)
    assert not at.exception
    assert "Next 24 h (forecast)" in texts(at)
    home = run(HOME, LIVE)
    assert "Weather · next 24 h" in texts(home)


def test_live_forecast_failure_keeps_the_history(live):
    live.setattr(shared, "build_weather_source", lambda mode, secrets=None: DEMO_WEATHER)
    failing = FakeForecast(fail=True)
    live.setattr(shared, "build_forecast_source", lambda mode, secrets=None: failing)
    at = run(WEATHER_PAGE, LIVE)
    assert not at.exception
    assert "(forecast)" not in texts(at)  # no outlook
    assert any("On big-change days" in str(h.value) for h in at.subheader)  # charts remain
