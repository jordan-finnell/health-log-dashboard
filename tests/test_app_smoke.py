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


def test_home_shows_a_tile_per_demo_metric(demo_config):
    at = AppTest.from_file(str(APP / "Home.py"), default_timeout=30).run()
    labels = [m.label for m in at.metric]
    for metric in demo_config.metrics:
        assert metric.label in labels


@pytest.mark.parametrize("page", PAGES)
def test_demo_mode_never_shows_the_real_schema(page, config):
    """Demo mode must use the generic demo schema, not the author's real column names."""
    at = AppTest.from_file(str(APP / page), default_timeout=30).run()
    shown = " ".join(
        [str(m.label) for m in at.metric]
        + [str(o) for ms in at.multiselect for o in ms.options]
        + [str(o) for sb in at.selectbox for o in sb.options]
    )
    for metric in config.metrics:
        assert metric.label not in shown


def test_trends_multi_select_switches_view(demo_config):
    at = AppTest.from_file(str(APP / "pages/1_Trends.py"), default_timeout=30).run()
    at.multiselect[0].set_value(demo_config.keys[:3]).run()
    assert not at.exception
    at.segmented_control(key="trend_view").set_value("Separate").run()
    assert not at.exception
