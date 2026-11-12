"""Helpers shared by every page: setup, auth gate, cached data loading, range filter."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import pandas as pd
import streamlit as st

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

log = logging.getLogger("health_log_dashboard")

RANGES: dict[str, int | None] = {"7d": 7, "30d": 30, "90d": 90, "1y": 365, "All": None}
CACHE_TTL_SECONDS = 600


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
