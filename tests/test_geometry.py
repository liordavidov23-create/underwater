"""בדיקות שגיאה בנקודה מול מספרי הייחוס (SPEC סעיף 6).

סבולת: ±0.005 מטר. אם בדיקה כאן נכשלת, מתקנים את המנוע ולא את הבדיקה.
"""

import math

import pytest

from nav_engine import (Buoy, ErrorParams, default_users, ellipse95, range_variance,
                        reference_buoys, solve, update_rate_hz)

TOL = 0.005

# (פריסה, פרמטרים, נקודה, שגיאה צפויה) מתוך SPEC סעיף 6
POINT_CASES = [
    ("around", {}, (165, 120), 0.733),
    ("around", {}, (232, 120), 0.722),
    ("west", {}, (165, 120), 0.830),
    ("west", {}, (232, 120), 1.161),
    ("chal", {}, (165, 120), 1.924),
    ("chal", {}, (232, 120), 3.204),
    ("solve", {}, (165, 120), 0.675),
    ("solve", {}, (232, 120), 0.893),
    ("west", {"mode": "unsync"}, (165, 120), 2.992),
    ("west", {"mode": "active"}, (165, 120), 0.753),
]


@pytest.mark.parametrize("layout,kw,point,expected", POINT_CASES)
def test_reference_point_error(layout, kw, point, expected):
    sol = solve(*point, reference_buoys(layout), ErrorParams(**kw))
    assert sol is not None
    assert sol.rms == pytest.approx(expected, abs=TOL)


@pytest.mark.parametrize("mode,n_buoys", [("sync", 1), ("unsync", 2), ("sync", 0), ("unsync", 0)])
def test_too_few_buoys_has_no_solution(mode, n_buoys):
    buoys = reference_buoys("around")[:n_buoys]
    assert solve(165, 120, buoys, ErrorParams(mode=mode)) is None


def test_minimum_buoys_gives_solution():
    b = reference_buoys("around")
    assert solve(165, 120, b[:2], ErrorParams(mode="sync")) is not None
    assert solve(165, 120, b[:3], ErrorParams(mode="unsync")) is not None


def test_singular_geometry_has_no_solution():
    # שני מצופים באותו מקום: כל השורות זהות, המטריצה סינגולרית
    buoys = [Buoy(50, 100), Buoy(50, 100)]
    assert solve(165, 120, buoys, ErrorParams()) is None


def test_range_variance_components():
    p = ErrorParams()
    r = 100.0
    base = 0.3 ** 2 + (0.002 * r) ** 2 + 0.5 ** 2
    assert range_variance(r, p) == pytest.approx(base + (1500 * 200e-6) ** 2)
    assert range_variance(r, ErrorParams(mode="unsync")) == pytest.approx(base)
    assert range_variance(r, ErrorParams(mode="active")) == pytest.approx(base)


def test_invalid_mode_rejected():
    with pytest.raises(ValueError):
        ErrorParams(mode="bogus")


# ערכים שחושבו ישירות מהמנוע ב-reference.html (פריסת west, ברירת מחדל)
def test_hdop_matches_reference_engine():
    sol = solve(165, 120, reference_buoys("west"), ErrorParams())
    assert sol.hdop == pytest.approx(1.166837, abs=1e-5)
    sol = solve(165, 120, reference_buoys("west"), ErrorParams(mode="unsync"))
    assert sol.hdop == pytest.approx(4.654435, abs=1e-5)


def test_ellipse_axes():
    e = ellipse95(4.0, 0.0, 1.0)
    assert e.semi_major == pytest.approx(2.447 * 2)
    assert e.semi_minor == pytest.approx(2.447 * 1)
    assert e.angle_rad == pytest.approx(0.0)
    e = ellipse95(1.0, 0.0, 4.0)
    assert abs(e.angle_rad) == pytest.approx(math.pi / 2)


def test_ellipse_consistent_with_rms():
    sol = solve(232, 120, reference_buoys("west"), ErrorParams())
    e = sol.ellipse
    assert math.hypot(e.semi_major, e.semi_minor) / 2.447 == pytest.approx(sol.rms)
    # מצופים ממערב: האליפסה מתארכת מצפון לדרום
    assert abs(abs(e.angle_rad) - math.pi / 2) < math.radians(20)


def test_update_rate_matches_reference_engine():
    b, u = reference_buoys("west"), default_users()
    assert update_rate_hz(b, u, ErrorParams(mode="sync")) == pytest.approx(1.382178, abs=1e-5)
    assert update_rate_hz(b, u, ErrorParams(mode="unsync")) == pytest.approx(1.382178, abs=1e-5)
    assert update_rate_hz(b, u, ErrorParams(mode="active")) == pytest.approx(0.641544, abs=1e-5)
    assert update_rate_hz([], u, ErrorParams()) == 0.0
