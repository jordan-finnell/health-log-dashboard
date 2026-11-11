"""Data sources. Each returns the *raw* sheet-shaped frame; ``transform.to_daily`` cleans it."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Protocol

import pandas as pd

from .config import ConfigError, MetricsConfig, Mode
from .synthetic import generate_raw

# Read-only: the app can never modify the sheet, even if the key leaks.
SHEETS_READONLY_SCOPE = "https://www.googleapis.com/auth/spreadsheets.readonly"


# Seed for the demo/README data. Chosen so the overview shows a mix of improving and
# worsening metrics (direction-aware colouring) and clear correlations in the Patterns page.
DEMO_SEED = 19


class DataSource(Protocol):
    def load_raw(self) -> pd.DataFrame: ...


@dataclass(frozen=True)
class SyntheticSource:
    config: MetricsConfig
    days: int = 180
    seed: int = DEMO_SEED
    end: date | None = None

    def load_raw(self) -> pd.DataFrame:
        return generate_raw(self.config, days=self.days, seed=self.seed, end=self.end)


@dataclass(frozen=True)
class CsvSource:
    path: Path

    def load_raw(self) -> pd.DataFrame:
        return pd.read_csv(self.path)


@dataclass(frozen=True)
class GSheetSource:
    """Reads one worksheet with a read-only service account. Never writes."""

    sheet_id: str
    worksheet: str
    service_account_info: Mapping[str, Any]

    def load_raw(self) -> pd.DataFrame:
        import gspread  # imported lazily so tests / demo mode never touch the network stack

        client = gspread.service_account_from_dict(
            dict(self.service_account_info), scopes=[SHEETS_READONLY_SCOPE]
        )
        sheet = client.open_by_key(self.sheet_id).worksheet(self.worksheet)
        values = sheet.get_all_values()  # strings as displayed; blanks are ""
        if not values:
            return pd.DataFrame()
        header, *rows = values
        return pd.DataFrame(rows, columns=header)


def build_source(
    mode: Mode,
    config: MetricsConfig,
    secrets: Mapping[str, Any] | None = None,
) -> DataSource:
    """Demo mode always yields synthetic data, so it can never read the real sheet."""
    if mode is Mode.DEMO:
        return SyntheticSource(config)
    if not secrets:
        raise ConfigError("live mode requires secrets")
    return GSheetSource(
        sheet_id=str(secrets["sheet_id"]),
        worksheet=str(secrets["worksheet"]),
        service_account_info=secrets["gcp_service_account"],
    )
