"""Metric configuration and live/demo mode resolution.

Deliberately free of Streamlit imports so it can be tested in isolation.
"""

from __future__ import annotations

import os
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"
METRICS_ENV_VAR = "PAIN_TRACKER_METRICS"

# Keys that must all be present in secrets.toml for live mode.
REQUIRED_SECRET_KEYS = ("gcp_service_account", "sheet_id", "worksheet", "app_password")


class ConfigError(ValueError):
    """Raised for invalid or incomplete configuration."""


class Mode(StrEnum):
    LIVE = "live"
    DEMO = "demo"


@dataclass(frozen=True)
class Metric:
    key: str
    column: str
    label: str
    min: float = 0
    max: float = 10
    higher_is_better: bool = False


@dataclass(frozen=True)
class MetricsConfig:
    timestamp_column: str
    metrics: tuple[Metric, ...]

    @property
    def keys(self) -> list[str]:
        return [m.key for m in self.metrics]

    def by_key(self, key: str) -> Metric:
        for m in self.metrics:
            if m.key == key:
                return m
        raise KeyError(key)


def default_metrics_path(environ: Mapping[str, str] | None = None) -> Path:
    """Env override, else config/metrics.toml, else the committed example."""
    environ = os.environ if environ is None else environ
    override = environ.get(METRICS_ENV_VAR)
    if override:
        return Path(override)
    private = CONFIG_DIR / "metrics.toml"
    return private if private.exists() else CONFIG_DIR / "metrics.example.toml"


def load_metrics(path: Path | str | None = None) -> MetricsConfig:
    path = Path(path) if path is not None else default_metrics_path()
    with path.open("rb") as fh:
        raw = tomllib.load(fh)

    try:
        timestamp_column = raw["timestamp"]["column"]
        entries = raw["metrics"]
    except KeyError as exc:
        raise ConfigError(f"{path}: missing required section/key {exc}") from exc

    metrics = []
    for entry in entries:
        missing = {"key", "column", "label"} - entry.keys()
        if missing:
            raise ConfigError(f"{path}: metric {entry!r} is missing {sorted(missing)}")
        try:
            metric = Metric(**entry)
        except TypeError as exc:
            raise ConfigError(f"{path}: invalid metric {entry!r}: {exc}") from exc
        if metric.min >= metric.max:
            raise ConfigError(f"{path}: metric {metric.key!r} has min >= max")
        metrics.append(metric)

    keys = [m.key for m in metrics]
    if len(set(keys)) != len(keys):
        raise ConfigError(f"{path}: duplicate metric keys")
    if not metrics:
        raise ConfigError(f"{path}: no metrics defined")
    return MetricsConfig(timestamp_column=timestamp_column, metrics=tuple(metrics))


def resolve_mode(
    secrets: Mapping[str, object] | None = None,
    environ: Mapping[str, str] | None = None,
) -> Mode:
    """Live if every required secret is present; demo otherwise.

    ``DEMO_MODE=1`` forces demo. A *partially* filled secrets file is an error rather
    than a silent fallback, so a typo can't quietly put the app into demo mode.
    """
    environ = os.environ if environ is None else environ
    if environ.get("DEMO_MODE", "").strip().lower() in {"1", "true", "yes"}:
        return Mode.DEMO

    present = [k for k in REQUIRED_SECRET_KEYS if secrets and k in secrets]
    if not present:
        return Mode.DEMO
    missing = [k for k in REQUIRED_SECRET_KEYS if k not in present]
    if missing:
        raise ConfigError(f"secrets are incomplete; missing: {', '.join(missing)}")
    return Mode.LIVE
