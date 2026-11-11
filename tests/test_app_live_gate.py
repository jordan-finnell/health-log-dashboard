"""Live mode must put everything behind the password and never touch data before login."""

from pathlib import Path

import pytest
from streamlit.proto.TextInput_pb2 import TextInput
from streamlit.testing.v1 import AppTest

import shared
from pain_tracker.sources import SyntheticSource

HOME = str(Path(__file__).resolve().parents[1] / "app" / "Home.py")
SECRETS = {
    "app_password": "s3cret-pw",
    "sheet_id": "SHEET",
    "worksheet": "Form Responses 1",
    "gcp_service_account": {"type": "service_account"},
}


@pytest.fixture
def live(monkeypatch):
    """A live-mode app whose 'Google Sheet' is synthetic data; records every load attempt."""
    monkeypatch.delenv("DEMO_MODE", raising=False)
    monkeypatch.setattr(shared.time, "sleep", lambda _s: None)
    loads = []

    def fake_build_source(mode, config, secrets=None):
        loads.append(mode)
        return SyntheticSource(config)

    monkeypatch.setattr(shared, "build_source", fake_build_source)
    shared._load_daily.clear()

    def make(secrets=SECRETS):
        at = AppTest.from_file(HOME, default_timeout=30)
        for key, value in secrets.items():
            at.secrets[key] = value
        return at

    make.loads = loads
    return make


def test_login_form_is_shown_and_no_data_is_loaded(live):
    at = live().run()
    assert not at.exception
    assert len(at.text_input) == 1
    assert at.text_input[0].proto.type == TextInput.PASSWORD  # input is masked
    assert len(at.metric) == 0  # nothing from the log is rendered
    assert live.loads == []  # the source was never even built


def test_wrong_password_is_rejected(live):
    at = live().run()
    at.text_input[0].input("nope")
    at.button[0].click().run()
    assert any("Incorrect" in e.value for e in at.error)
    assert len(at.metric) == 0
    assert live.loads == []


def test_correct_password_unlocks_the_dashboard(live):
    at = live().run()
    at.text_input[0].input(SECRETS["app_password"])
    at.button[0].click().run()
    assert not at.exception
    assert at.session_state["authed"] is True
    assert len(at.metric) >= 6  # the stat tiles are now visible
    assert live.loads  # the source was built only after login


def test_gate_applies_to_every_page(live):
    page = str(Path(HOME).parent / "pages" / "4_Data.py")
    at = AppTest.from_file(page, default_timeout=30)
    for key, value in SECRETS.items():
        at.secrets[key] = value
    at.run()
    assert len(at.text_input) == 1
    assert live.loads == []


def test_partial_secrets_refuse_to_start(live):
    partial = {k: v for k, v in SECRETS.items() if k != "app_password"}
    at = live(partial).run()
    assert any("app_password" in e.value for e in at.error)
    assert len(at.metric) == 0
    assert live.loads == []
