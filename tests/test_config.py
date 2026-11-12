import pytest

from health_log_dashboard.config import (
    CONFIG_DIR,
    ConfigError,
    Mode,
    default_metrics_path,
    load_metrics,
    load_metrics_for,
    password_enabled,
    resolve_mode,
)

FULL_SECRETS = {
    "gcp_service_account": {"type": "service_account"},
    "sheet_id": "x",
    "worksheet": "Sheet1",
    "app_password": "pw",
}


def test_example_config_loads(config):
    assert config.timestamp_column == "Timestamp"
    assert len(config.metrics) == 6
    assert config.by_key("excitement").higher_is_better is True
    assert config.by_key("anxiety").higher_is_better is False


def test_duplicate_keys_rejected(tmp_path):
    p = tmp_path / "m.toml"
    p.write_text(
        '[timestamp]\ncolumn="T"\n'
        '[[metrics]]\nkey="a"\ncolumn="A"\nlabel="A"\n'
        '[[metrics]]\nkey="a"\ncolumn="B"\nlabel="B"\n'
    )
    with pytest.raises(ConfigError, match="duplicate"):
        load_metrics(p)


def test_unknown_metric_field_is_config_error(tmp_path):
    p = tmp_path / "m.toml"
    p.write_text('[timestamp]\ncolumn="T"\n[[metrics]]\nkey="a"\ncolumn="A"\nlabel="A"\nbogus=1\n')
    with pytest.raises(ConfigError, match="invalid metric"):
        load_metrics(p)


def test_bad_scale_rejected(tmp_path):
    p = tmp_path / "m.toml"
    p.write_text(
        '[timestamp]\ncolumn="T"\n[[metrics]]\nkey="a"\ncolumn="A"\nlabel="A"\nmin=5\nmax=5\n'
    )
    with pytest.raises(ConfigError, match="min >= max"):
        load_metrics(p)


def test_default_path_env_override_and_fallback(tmp_path):
    assert default_metrics_path({"HEALTH_LOG_DASHBOARD_METRICS": str(tmp_path / "x.toml")}) == (
        tmp_path / "x.toml"
    )
    assert default_metrics_path({}).parent == CONFIG_DIR


def test_mode_demo_without_secrets():
    assert resolve_mode(None, {}) is Mode.DEMO
    assert resolve_mode({}, {}) is Mode.DEMO


def test_mode_live_with_full_secrets():
    assert resolve_mode(FULL_SECRETS, {}) is Mode.LIVE


def test_demo_mode_env_forces_demo_even_with_secrets():
    assert resolve_mode(FULL_SECRETS, {"DEMO_MODE": "1"}) is Mode.DEMO
    assert resolve_mode(FULL_SECRETS, {"DEMO_MODE": "TRUE"}) is Mode.DEMO


def test_partial_secrets_is_an_error_not_silent_demo():
    partial = {k: v for k, v in FULL_SECRETS.items() if k != "sheet_id"}
    with pytest.raises(ConfigError, match="sheet_id"):
        resolve_mode(partial, {})


def test_password_is_optional_for_live_mode():
    no_password = {k: v for k, v in FULL_SECRETS.items() if k != "app_password"}
    assert resolve_mode(no_password, {}) is Mode.LIVE
    assert password_enabled(no_password) is False
    assert password_enabled(FULL_SECRETS) is True


@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_password_is_an_error_not_an_open_door(blank):
    """A mistyped/empty value must not quietly disable the gate; removing the key does that."""
    with pytest.raises(ConfigError, match="app_password"):
        resolve_mode({**FULL_SECRETS, "app_password": blank}, {})
    assert password_enabled({"app_password": blank}) is False


def test_password_alone_does_not_make_live_mode():
    assert resolve_mode({"app_password": "pw"}, {}) is Mode.DEMO


def test_demo_schema_has_five_metrics_with_both_directions(demo_config):
    assert len(demo_config.metrics) == 5
    better_high = [m for m in demo_config.metrics if m.higher_is_better]
    better_low = [m for m in demo_config.metrics if not m.higher_is_better]
    assert len(better_high) >= 2 and len(better_low) >= 2


def test_demo_schema_is_different_from_the_real_one(config, demo_config):
    """The public demo must not reuse the author's real metric names or column headers."""
    assert not set(demo_config.keys) & set(config.keys)
    real_columns = {m.column.lower() for m in config.metrics}
    assert not {m.column.lower() for m in demo_config.metrics} & real_columns
    assert not {m.label.lower() for m in demo_config.metrics} & {
        m.label.lower() for m in config.metrics
    }


def test_load_metrics_for_mode(config, demo_config):
    assert load_metrics_for(Mode.DEMO).keys == demo_config.keys
    # live mode follows the normal resolution (env override > metrics.toml > example)
    live = load_metrics_for(
        Mode.LIVE, {"HEALTH_LOG_DASHBOARD_METRICS": str(CONFIG_DIR / "demo.toml")}
    )
    assert live.keys == demo_config.keys
    assert load_metrics_for(Mode.LIVE, {}).keys  # resolves to a real file
