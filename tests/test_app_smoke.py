"""Run every Streamlit page headlessly in demo mode and assert nothing raises."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "app"
PAGES = [
    "Home.py",
    "pages/1_Trends.py",
    "pages/2_Calendar.py",
    "pages/3_Patterns.py",
    "pages/4_Data.py",
]


@pytest.fixture(autouse=True)
def demo_mode(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "1")


@pytest.mark.parametrize("page", PAGES)
def test_page_renders_in_demo_mode(page):
    at = AppTest.from_file(str(APP / page), default_timeout=30).run()
    assert not at.exception, [e.value for e in at.exception]
    assert any("Demo mode" in str(i.value) for i in at.sidebar.info)


def test_home_shows_a_tile_per_metric(config):
    at = AppTest.from_file(str(APP / "Home.py"), default_timeout=30).run()
    labels = [m.label for m in at.metric]
    for metric in config.metrics:
        assert metric.label in labels


def test_trends_multi_select_switches_view():
    at = AppTest.from_file(str(APP / "pages/1_Trends.py"), default_timeout=30).run()
    at.multiselect[0].set_value(["headache", "fatigue", "anxiety"]).run()
    assert not at.exception
    at.segmented_control(key="trend_view").set_value("Separate").run()
    assert not at.exception
