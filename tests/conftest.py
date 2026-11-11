from datetime import date

import pytest

from pain_tracker.config import CONFIG_DIR, DEMO_METRICS_PATH, MetricsConfig, load_metrics

FIXED_END = date(2026, 1, 31)


@pytest.fixture(scope="session")
def config() -> MetricsConfig:
    # Always the committed example, never a developer's private config/metrics.toml.
    return load_metrics(CONFIG_DIR / "metrics.example.toml")


@pytest.fixture(scope="session")
def demo_config() -> MetricsConfig:
    """The generic schema used by demo mode and the README screenshots."""
    return load_metrics(DEMO_METRICS_PATH)
