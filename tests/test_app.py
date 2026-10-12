"""בדיקות עשן לאפליקציה דרך AppTest של Streamlit (בלי דפדפן)."""

import pytest

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest


def _run(at=None):
    at = at or AppTest.from_file("app.py", default_timeout=30)
    at.run()
    assert not at.exception, at.exception
    return at


def _html(at) -> str:
    return "\n".join(m.value for m in at.markdown)


def _load(at, layout):
    at.selectbox(key="layout_choice").set_value(layout)
    next(b for b in at.button if b.label == "טען פריסה").click()
    return _run(at)


def test_app_starts_with_west():
    at = _run()
    assert "61.7%" in _html(at)


@pytest.mark.parametrize("layout,expected", [("west", "61.7%"), ("around", "100.0%"),
                                             ("chal", "5.2%"), ("solve", "85.6%")])
def test_load_reference_layout_shows_coverage(layout, expected):
    at = _load(_run(), layout)
    assert expected in _html(at)


def test_mode_switch_active():
    at = _run()
    at.radio(key="mode").set_value("active")
    at = _run(at)
    assert "70.8%" in _html(at)


def test_model_note_shown():
    assert "הערכה ממודל" in _html(_run())
