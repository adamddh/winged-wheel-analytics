"""Smoke-test the dashboard against the committed gold exports, headlessly."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = Path(__file__).parent.parent / "app" / "streamlit_app.py"


def test_dashboard_renders_real_exports():
    at = AppTest.from_file(str(APP), default_timeout=60).run()
    assert not at.exception, at.exception
    html = " ".join(str(h.proto.body) for h in at.get("html"))
    assert "Detroit," in html and "expected goals" in html
    assert len(at.tabs) == 4
    assert at.selectbox[0].options  # game picker lists Red Wings games
