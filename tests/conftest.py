from datetime import date

import pytest

from pain_tracker.config import CONFIG_DIR, MetricsConfig, load_metrics

FIXED_END = date(2026, 1, 31)


@pytest.fixture(scope="session")
def config() -> MetricsConfig:
    # Always the committed example, never a developer's private config/metrics.toml.
    return load_metrics(CONFIG_DIR / "metrics.example.toml")
