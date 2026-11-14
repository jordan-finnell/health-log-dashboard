"""Helpers shared by every page: setup, auth gate, cached data loading, range filter."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd
import streamlit as st
from winds_of_change import Outlook, WeatherError, convert, daily_weather, outlook

from health_log_dashboard.auth import verify_password
from health_log_dashboard.charts import PLOT_CONFIG, Theme, theme_for
from health_log_dashboard.config import (
    ConfigError,
    MetricsConfig,
    Mode,
    load_metrics_for,
    password_enabled,
    resolve_mode,
)
from health_log_dashboard.sources import build_source
from health_log_dashboard.transform import to_daily
from health_log_dashboard.weather import (
    DISPLAY_UNITS,
    WINDOWS,
    build_forecast_source,
    build_weather_source,
)

log = logging.getLogger("health_log_dashboard")

RANGES: dict[str, int | None] = {"7d": 7, "30d": 30, "90d": 90, "1y": 365, "All": None}
CACHE_TTL_SECONDS = 600
# Weather updates every 6 h. Failures are cached too, so an offline home page doesn't wait
# out a timeout on every load; "Refresh data" retries at once.
WEATHER_TTL_SECONDS = 900


@dataclass(frozen=True)
class Context:
    config: MetricsConfig
    mode: Mode
    theme: Theme

    @property
    def color_index(self) -> dict[str, int]:
        """Metric key -> categorical slot. Fixed by config order, never by selection."""
        return {m.key: i for i, m in enumerate(self.config.metrics)}


def _secrets() -> dict:
    try:
        return dict(st.secrets)
    except Exception:  # no secrets file -> demo mode
        return {}


@st.cache_resource
def _config(mode_value: str) -> MetricsConfig:
    """Demo mode uses the generic demo schema; live mode uses the real log's mapping."""
    return load_metrics_for(Mode(mode_value))


def _theme() -> Theme:
    try:
        name = st.context.theme.type
    except Exception:
        name = None
    return theme_for(name)


def _gate(mode: Mode) -> None:
    """If a password is configured, require it before anything (including data) is loaded."""
    if mode is not Mode.LIVE or not password_enabled(_secrets()) or st.session_state.get("authed"):
        return
    st.title("Health Log Dashboard")
    with st.form("login"):
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Unlock", type="primary")
    if submitted:
        if verify_password(password, str(_secrets().get("app_password", ""))):
            st.session_state["authed"] = True
            st.rerun()
        time.sleep(1)  # slow down guessing
        st.error("Incorrect password.")
    st.stop()


def page_setup(title: str, icon: str = ":material/monitor_heart:") -> Context:
    """Call first on every page. Handles config, mode, auth and the sidebar."""
    st.set_page_config(page_title=f"{title} · Health Log Dashboard", page_icon=icon)
    try:
        mode = resolve_mode(_secrets())
    except ConfigError as exc:
        st.error(f"Configuration problem: {exc}")
        st.stop()
    _gate(mode)

    with st.sidebar:
        if mode is Mode.DEMO:
            st.info("Demo mode: synthetic data only.", icon=":material/science:")
        elif not password_enabled(_secrets()):
            # Make it obvious if the gate is off, e.g. because a key name was mistyped.
            st.warning(
                "No password set: anyone who can reach this page can see the log.",
                icon=":material/lock_open:",
            )
        st.button(
            "Refresh data",
            icon=":material/refresh:",
            on_click=st.cache_data.clear,
            width="stretch",
            help="Re-read the log now instead of waiting for the cache to expire.",
        )
    return Context(config=_config(mode.value), mode=mode, theme=_theme())


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner="Loading log…")
def _load_daily(mode_value: str) -> pd.DataFrame:
    config = _config(mode_value)
    mode = Mode(mode_value)
    source = build_source(mode, config, _secrets() if mode is Mode.LIVE else None)
    return to_daily(source.load_raw(), config)


def load_daily(ctx: Context) -> pd.DataFrame:
    """The cleaned daily frame. Stops the page with a short message if it can't be loaded."""
    try:
        daily = _load_daily(ctx.mode.value)
    except Exception as exc:
        log.exception("failed to load data")  # full detail goes to the server log only
        st.error(f"Couldn't load the log ({type(exc).__name__}). See the server logs.")
        st.stop()
    if daily.empty:
        st.warning("The log has no readable entries yet.")
        st.stop()
    return daily


def range_filter(options: tuple[str, ...] = tuple(RANGES), default: str = "90d") -> int | None:
    """One date-range row above the content it scopes. Persists across pages."""
    choice = st.segmented_control(
        "Date range",
        list(options),
        default=default,
        required=True,
        key="range",
        persist_state="session",
        label_visibility="collapsed",
        width="stretch",
    )
    return RANGES.get(choice, RANGES[default])


def show_chart(fig, key: str | None = None) -> None:
    """Render a Plotly figure with the touch-friendly config and no Streamlit re-theming."""
    st.plotly_chart(fig, config=PLOT_CONFIG, theme=None, width="stretch", key=key)


def display_table(df: pd.DataFrame, config: MetricsConfig) -> pd.DataFrame:
    """Daily frame with readable column labels and ISO dates, newest first."""
    labels = {m.key: m.label for m in config.metrics}
    shown = df.rename(columns=labels).sort_index(ascending=False)
    shown.index = shown.index.strftime("%Y-%m-%d")
    shown.index.name = "Date"
    return shown


def styled(table: pd.DataFrame):
    """Whole-number ratings, with a dash (not "None") for days/metrics with no entry."""
    return table.style.format("{:.0f}", na_rep="–")


def table_view(df: pd.DataFrame, config: MetricsConfig, *, label: str = "Table view") -> None:
    """A text/table twin for a chart, so no value is reachable only through colour or hover."""
    with st.expander(label, icon=":material/table:"):
        st.dataframe(styled(display_table(df, config)), width="stretch")


# ------------------------------------------------------------------------------ weather


@dataclass(frozen=True)
class WeatherData:
    hourly: pd.DataFrame  # archive: tz-aware local hours, display units, the whole log
    daily: pd.DataFrame  # one row per day: daily means and peak w-hour changes
    synthetic: bool
    # Outlook series reaching past now: the forecast (live) or the synthetic series (demo).
    # Changes are measured within it and ranked against `hourly`. None if unavailable.
    recent: pd.DataFrame | None = None

    def outlook(self, key: str, hours: int, now: pd.Timestamp | None = None) -> Outlook | None:
        if self.recent is None or key not in self.recent:
            return None
        now = now if now is not None else pd.Timestamp.now(tz=self.recent.index.tz)
        return outlook(self.recent, key, now, hours, history=self.hourly)


@dataclass(frozen=True)
class WeatherResult:
    data: WeatherData | None
    problem: str | None = None  # None, "unconfigured", "config" or "fetch"
    message: str = ""


@st.cache_data(ttl=WEATHER_TTL_SECONDS, show_spinner="Loading weather…")
def _load_weather(mode_value: str, start: date, end: date) -> WeatherResult:
    """Secrets (and so the location) are read in here, never passed in the cache key."""
    mode = Mode(mode_value)
    try:
        source = build_weather_source(mode, _secrets() if mode is Mode.LIVE else None)
    except ConfigError as exc:
        return WeatherResult(None, "config", str(exc))
    if source is None:
        return WeatherResult(None, "unconfigured")
    try:
        hourly = convert(source.load_hourly(start, end), DISPLAY_UNITS)
    except WeatherError as exc:  # message carries no location by design
        log.warning("weather unavailable: %s", exc)
        return WeatherResult(None, "fetch", str(exc))
    daily = daily_weather(hourly, WINDOWS)
    recent = hourly if mode is Mode.DEMO else None
    forecast = build_forecast_source(mode, _secrets() if mode is Mode.LIVE else None)
    if forecast is not None:
        try:
            recent = convert(forecast.load_recent(), DISPLAY_UNITS)
        except WeatherError as exc:  # history still works; only the outlook is lost
            log.warning("weather forecast unavailable: %s", exc)
    return WeatherResult(WeatherData(hourly, daily, mode is Mode.DEMO, recent))


def load_weather(ctx: Context, daily: pd.DataFrame, *, quiet: bool = False) -> WeatherData | None:
    """Weather covering the whole log plus the coming day, or None (with a short message
    unless ``quiet``). Never stops the page: weather is optional."""
    start = date(daily.index.min().year, 1, 1)  # whole years: the exact log start stays local
    end = date.today() + timedelta(days=2)  # the archive clamps this to what it has
    try:
        result = _load_weather(ctx.mode.value, start, end)
    except Exception as exc:
        log.exception("failed to load weather")
        result = WeatherResult(None, "fetch", type(exc).__name__)
    if result.data is not None or quiet:
        return result.data
    if result.problem == "unconfigured":
        st.info(
            "Weather isn't set up. Add a `[weather]` section with `latitude` and `longitude` "
            "to secrets.toml (see `.streamlit/secrets.toml.example`).",
            icon=":material/cloud_off:",
        )
    elif result.problem == "config":
        st.error(f"Weather settings problem: {result.message}")
    else:
        st.warning(
            f"Couldn't load weather right now ({result.message}). It retries in a few minutes.",
            icon=":material/cloud_off:",
        )
    return None
