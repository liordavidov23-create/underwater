"""מפת שגיאה ואחוז כיסוי (SPEC סעיף 4.5)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from .geometry import solve_grid
from .models import Buoy, ErrorParams, WorkArea

GRID_STEP = 2.0     # מטר
TARGET_ERROR = 1.0  # מטר


@dataclass
class ErrorMap:
    xs: np.ndarray   # מרכזי עמודות, מטר
    ys: np.ndarray   # מרכזי שורות, מטר
    rms: np.ndarray  # צורה (len(ys), len(xs)). nan היכן שאין פתרון


def cell_centers(lo: float, hi: float, step: float = GRID_STEP) -> np.ndarray:
    """מרכזי תאים בגודל step בין lo ל-hi: lo+step/2, lo+3*step/2, ..."""
    n = int(np.floor((hi - lo) / step + 1e-9))
    return lo + step / 2 + step * np.arange(n)


def error_grid(xs: np.ndarray, ys: np.ndarray, buoys: Sequence[Buoy],
               params: ErrorParams) -> ErrorMap:
    X, Y = np.meshgrid(np.asarray(xs, float), np.asarray(ys, float))
    return ErrorMap(xs=np.asarray(xs, float), ys=np.asarray(ys, float),
                    rms=solve_grid(X, Y, buoys, params)["rms"])


def error_map(x0: float, y0: float, x1: float, y1: float, buoys: Sequence[Buoy],
              params: ErrorParams, step: float = GRID_STEP) -> ErrorMap:
    """מפת שגיאה במרכזי תאים בגודל step בתוך המלבן הנתון."""
    return error_grid(cell_centers(x0, x1, step), cell_centers(y0, y1, step), buoys, params)


def coverage(buoys: Sequence[Buoy], params: ErrorParams, area: WorkArea | None = None,
             step: float = GRID_STEP, target: float = TARGET_ERROR) -> float:
    """אחוז הנקודות בשטח העבודה שבהן השגיאה קטנה מ-target (0 עד 100)."""
    area = area or WorkArea()
    m = error_map(area.x0, area.y0, area.x1, area.y1, buoys, params, step)
    if m.rms.size == 0:
        return 0.0
    good = np.nan_to_num(m.rms, nan=np.inf) < target
    return float(100.0 * good.mean())
