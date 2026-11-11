import pytest

from pain_tracker.config import (
    CONFIG_DIR,
    ConfigError,
    Mode,
    default_metrics_path,
    load_metrics,
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
    assert default_metrics_path({"PAIN_TRACKER_METRICS": str(tmp_path / "x.toml")}) == (
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
    partial = {k: v for k, v in FULL_SECRETS.items() if k != "app_password"}
    with pytest.raises(ConfigError, match="app_password"):
        resolve_mode(partial, {})
