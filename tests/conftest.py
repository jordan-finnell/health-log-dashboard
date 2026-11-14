import urllib.request
from datetime import date

import pytest

from health_log_dashboard.config import CONFIG_DIR, DEMO_METRICS_PATH, MetricsConfig, load_metrics

FIXED_END = date(2026, 1, 31)


@pytest.fixture(scope="session")
def config() -> MetricsConfig:
    # Always the committed example, never a developer's private config/metrics.toml.
    return load_metrics(CONFIG_DIR / "metrics.example.toml")


@pytest.fixture(scope="session")
def demo_config() -> MetricsConfig:
    """The generic schema used by demo mode and the README screenshots."""
    return load_metrics(DEMO_METRICS_PATH)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """No test may reach the network (weather included): demo and tests are offline."""

    def blocked(*_args, **_kwargs):
        raise AssertionError("network access attempted in a test")

    monkeypatch.setattr(urllib.request, "urlopen", blocked)
