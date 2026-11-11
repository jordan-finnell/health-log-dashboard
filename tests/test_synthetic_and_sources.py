import sys
import types

import pandas as pd
import pytest

from health_log_dashboard.config import ConfigError, Mode
from health_log_dashboard.sources import (
    SHEETS_READONLY_SCOPE,
    CsvSource,
    GSheetSource,
    SyntheticSource,
    build_source,
)
from health_log_dashboard.synthetic import generate_raw
from health_log_dashboard.transform import to_daily

from .conftest import FIXED_END


def test_synthetic_is_deterministic_per_seed(config):
    a = generate_raw(config, days=60, end=FIXED_END, seed=7)
    b = generate_raw(config, days=60, end=FIXED_END, seed=7)
    c = generate_raw(config, days=60, end=FIXED_END, seed=8)
    pd.testing.assert_frame_equal(a, b)
    assert not a.equals(c)


def test_synthetic_has_sheet_shape_and_quirks(config):
    raw = generate_raw(config, days=200, end=FIXED_END, seed=1)
    assert list(raw.columns) == [config.timestamp_column, *(m.column for m in config.metrics)]
    ts = raw[config.timestamp_column]
    assert ":" not in ts.iloc[0]  # first row is date-only
    assert ts.iloc[1:].str.contains(":").all()
    # late-starting metric is blank for the first half
    assert raw["Neck Pain"].iloc[:20].isna().all()
    assert raw["Neck Pain"].iloc[-20:].notna().any()


def test_synthetic_round_trips_through_transform(config):
    raw = generate_raw(config, days=120, end=FIXED_END, seed=3)
    daily = to_daily(raw, config)
    # one row per calendar day, ends near the requested end date
    assert daily.index.is_monotonic_increasing
    assert daily.index.to_series().diff().dropna().eq(pd.Timedelta("1D")).all()
    assert daily.index.max() <= pd.Timestamp(FIXED_END)
    for m in config.metrics:
        col = daily[m.key].dropna()
        assert col.between(m.min, m.max).all()
    # some days were missed, and duplicates were collapsed
    assert daily["headache"].isna().any()
    assert len(daily) <= 120


def test_synthetic_rejects_bad_days(config):
    with pytest.raises(ValueError):
        generate_raw(config, days=0)


def test_csv_source_reads_file(tmp_path):
    p = tmp_path / "log.csv"
    p.write_text("Timestamp,Anxiety\n3/1/2026 9:00:00,4\n")
    assert CsvSource(p).load_raw()["Anxiety"].tolist() == [4]


def test_build_source_demo_never_returns_a_sheet_source(config):
    # Even if real secrets were passed, demo mode must stay synthetic.
    secrets = {"sheet_id": "s", "worksheet": "w", "gcp_service_account": {"a": 1}}
    assert isinstance(build_source(Mode.DEMO, config, secrets), SyntheticSource)


def test_build_source_live_requires_secrets(config):
    with pytest.raises(ConfigError):
        build_source(Mode.LIVE, config, None)


def test_gsheet_source_uses_readonly_scope_and_builds_frame(monkeypatch, config):
    calls = {}

    class FakeWorksheet:
        def get_all_values(self):
            return [["Timestamp", "Anxiety"], ["3/1/2026 9:00:00", "4"], ["3/2/2026 9:00:00", ""]]

    class FakeSheet:
        def worksheet(self, name):
            calls["worksheet"] = name
            return FakeWorksheet()

    class FakeClient:
        def open_by_key(self, key):
            calls["key"] = key
            return FakeSheet()

    def fake_from_dict(info, scopes):
        calls["scopes"] = scopes
        calls["info"] = info
        return FakeClient()

    fake_gspread = types.SimpleNamespace(service_account_from_dict=fake_from_dict)
    monkeypatch.setitem(sys.modules, "gspread", fake_gspread)

    src = build_source(
        Mode.LIVE,
        config,
        {"sheet_id": "SHEET", "worksheet": "Form Responses 1", "gcp_service_account": {"k": "v"}},
    )
    assert isinstance(src, GSheetSource)
    raw = src.load_raw()

    assert calls["scopes"] == [SHEETS_READONLY_SCOPE]
    assert calls["key"] == "SHEET"
    assert calls["worksheet"] == "Form Responses 1"
    assert raw.columns.tolist() == ["Timestamp", "Anxiety"]
    assert raw["Anxiety"].tolist() == ["4", ""]


def test_gsheet_source_empty_sheet(monkeypatch):
    class WS:
        def get_all_values(self):
            return []

    client = types.SimpleNamespace(
        open_by_key=lambda k: types.SimpleNamespace(worksheet=lambda n: WS())
    )
    monkeypatch.setitem(
        sys.modules,
        "gspread",
        types.SimpleNamespace(service_account_from_dict=lambda info, scopes: client),
    )
    assert GSheetSource("s", "w", {}).load_raw().empty


def test_readonly_scope_is_not_write_scope():
    assert SHEETS_READONLY_SCOPE.endswith("spreadsheets.readonly")


def test_synthetic_works_for_the_demo_schema(demo_config):
    raw = generate_raw(demo_config, days=150, end=FIXED_END, seed=5)
    assert list(raw.columns) == [
        demo_config.timestamp_column,
        *(m.column for m in demo_config.metrics),
    ]
    last = demo_config.metrics[-1]
    assert raw[last.column].iloc[:20].isna().all()  # last metric starts partway through
    assert raw[demo_config.metrics[0].column].notna().all()
    daily = to_daily(raw, demo_config)
    for m in demo_config.metrics:
        assert daily[m.key].dropna().between(m.min, m.max).all()


def test_synthetic_demo_metrics_move_in_the_expected_directions(demo_config):
    """Good scores fall when bad ones rise: the demo should look like a coherent person."""
    daily = to_daily(generate_raw(demo_config, days=400, end=FIXED_END, seed=2), demo_config)
    corr = daily.corr(method="spearman")
    assert corr.loc["stress", "sleep_quality"] < -0.2
    assert corr.loc["stress", "soreness"] > 0.2
    assert corr.loc["energy", "focus"] > 0.2
