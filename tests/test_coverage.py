"""בדיקות אחוז כיסוי מול מספרי הייחוס (SPEC סעיף 6).

סבולת: ±0.5 נקודות אחוז. אם בדיקה כאן נכשלת, מתקנים את המנוע ולא את הבדיקה.
"""

import numpy as np
import pytest

from nav_engine import ErrorParams, WorkArea, coverage, error_map, reference_buoys
from nav_engine.coverage import cell_centers

TOL = 0.5

COVERAGE_CASES = [
    ("around", {}, 100.0),
    ("west", {}, 61.7),
    ("chal", {}, 5.2),
    ("solve", {}, 85.6),
    ("west", {"mode": "unsync"}, 0.1),
    ("west", {"mode": "active"}, 70.8),
    ("west", {"sigma_gnss": 0.05}, 88.4),
    ("chal", {"sigma_gnss": 0.05}, 17.9),
]


@pytest.mark.parametrize("layout,kw,expected", COVERAGE_CASES)
def test_reference_coverage(layout, kw, expected):
    assert coverage(reference_buoys(layout), ErrorParams(**kw)) == pytest.approx(expected, abs=TOL)


def test_grid_is_cell_centers():
    xs = cell_centers(70, 270)
    assert xs[0] == 71 and xs[1] == 73 and xs[-1] == 269 and len(xs) == 100
    assert len(cell_centers(45, 195)) == 75


def test_no_solution_counts_as_uncovered():
    b = reference_buoys("west")[:1]
    assert coverage(b, ErrorParams()) == 0.0
    m = error_map(0, 0, 20, 20, b, ErrorParams())
    assert np.isnan(m.rms).all()


def test_custom_area():
    area = WorkArea(70, 45, 170, 195)
    assert coverage(reference_buoys("around"), ErrorParams(), area) == pytest.approx(100.0)
