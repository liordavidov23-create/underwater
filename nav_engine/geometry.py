"""קווריאנס המיקום, שגיאה אופקית, HDOP ואליפסת 95% (SPEC סעיפים 4.2 עד 4.4).

הליבה מחושבת בצורה וקטורית על מערך נקודות, כך שאותו קוד משמש גם לנקודה בודדת
וגם למפת שגיאה שלמה.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

import numpy as np

from .models import SOUND_SPEED, Buoy, ErrorParams

DET_EPS = 1e-12      # מתחת לזה המטריצה נחשבת סינגולרית
ELLIPSE_K95 = 2.447  # מקדם לאליפסת 95% בדו-ממד


@dataclass
class Ellipse:
    semi_major: float  # מטר
    semi_minor: float  # מטר
    angle_rad: float   # זווית הציר הארוך מציר x, נגד כיוון השעון


@dataclass
class Solution:
    cxx: float
    cxy: float
    cyy: float
    rms: float   # שגיאה אופקית 1σ במטרים
    hdop: float  # inf אם הגאומטריה לא פתירה

    @property
    def cov(self) -> np.ndarray:
        return np.array([[self.cxx, self.cxy], [self.cxy, self.cyy]])

    @property
    def ellipse(self) -> Ellipse:
        return ellipse95(self.cxx, self.cxy, self.cyy)


def _buoy_xy(buoys: Sequence[Buoy]) -> tuple[np.ndarray, np.ndarray]:
    bx = np.array([b.x for b in buoys], dtype=float)
    by = np.array([b.y for b in buoys], dtype=float)
    return bx, by


def _dz(params: ErrorParams) -> float:
    return params.user_depth - params.transducer_depth


def range_variance(r, params: ErrorParams):
    """שונות שגיאת הטווח (מטר²) עבור טווח משופע r."""
    s2 = params.sigma_range ** 2 + (params.sound_speed_frac * r) ** 2 + params.sigma_gnss ** 2
    if params.mode == "sync":
        s2 = s2 + (SOUND_SPEED * params.sigma_clock) ** 2
    return s2


def _horizontal_cov(N: dict[str, np.ndarray], dim: int):
    """היפוך N והחזרת תת-המטריצה האופקית (cxx, cxy, cyy) ודגל תקינות."""
    xx, xy, yy = N["xx"], N["xy"], N["yy"]
    if dim == 2:
        det = xx * yy - xy * xy
        ok = np.isfinite(det) & (np.abs(det) >= DET_EPS)
        safe = np.where(ok, det, 1.0)
        return yy / safe, -xy / safe, xx / safe, ok
    xb, yb, bb = N["xb"], N["yb"], N["bb"]
    c00 = yy * bb - yb * yb
    c01 = yb * xb - xy * bb
    c02 = xy * yb - yy * xb
    det = xx * c00 + xy * c01 + xb * c02
    ok = np.isfinite(det) & (np.abs(det) >= DET_EPS)
    safe = np.where(ok, det, 1.0)
    c11 = xx * bb - xb * xb
    return c00 / safe, c01 / safe, c11 / safe, ok


def solve_grid(px, py, buoys: Sequence[Buoy], params: ErrorParams):
    """פתרון וקטורי על מערכי נקודות px, py באותה צורה.

    מחזיר מילון עם cxx, cxy, cyy, rms, hdop ו-valid. בנקודות שאין בהן פתרון
    rms הוא nan ו-valid הוא False.
    """
    px = np.asarray(px, dtype=float)
    py = np.asarray(py, dtype=float)
    dim = 3 if params.mode == "unsync" else 2
    shape = np.broadcast(px, py).shape
    nan = np.full(shape, np.nan)
    if len(buoys) < dim:
        return {"cxx": nan, "cxy": nan, "cyy": nan, "rms": nan,
                "hdop": np.full(shape, np.inf), "valid": np.zeros(shape, dtype=bool)}

    bx, by = _buoy_xy(buoys)
    dx = px[..., None] - bx
    dy = py[..., None] - by
    dz = _dz(params)
    r = np.maximum(1.0, np.sqrt(dx * dx + dy * dy + dz * dz))
    hx, hy = dx / r, dy / r
    w = 1.0 / range_variance(r, params)

    def normal(weights):
        n = {"xx": (weights * hx * hx).sum(-1), "xy": (weights * hx * hy).sum(-1),
             "yy": (weights * hy * hy).sum(-1)}
        if dim == 3:
            n["xb"] = (weights * hx).sum(-1)
            n["yb"] = (weights * hy).sum(-1)
            n["bb"] = np.broadcast_to(weights, hx.shape).sum(-1)
        return n

    cxx, cxy, cyy, ok = _horizontal_cov(normal(w), dim)
    ok = ok & (cxx >= 0) & (cyy >= 0)
    rms = np.where(ok, np.sqrt(np.where(ok, cxx + cyy, 0.0)), np.nan)

    uxx, _, uyy, uok = _horizontal_cov(normal(np.ones_like(r)), dim)
    hdop = np.where(uok, np.sqrt(np.maximum(np.where(uok, uxx + uyy, 0.0), 0.0)), np.inf)

    return {"cxx": np.where(ok, cxx, np.nan), "cxy": np.where(ok, cxy, np.nan),
            "cyy": np.where(ok, cyy, np.nan), "rms": rms, "hdop": hdop, "valid": ok}


def solve(x: float, y: float, buoys: Sequence[Buoy], params: ErrorParams) -> Solution | None:
    """שגיאה בנקודה אחת. מחזיר None כשאין פתרון."""
    g = solve_grid(np.array(x), np.array(y), buoys, params)
    if not bool(g["valid"]):
        return None
    return Solution(cxx=float(g["cxx"]), cxy=float(g["cxy"]), cyy=float(g["cyy"]),
                    rms=float(g["rms"]), hdop=float(g["hdop"]))


def ellipse95(cxx: float, cxy: float, cyy: float) -> Ellipse:
    """אליפסת 95% מתוך הקווריאנס האופקית."""
    tr = cxx + cyy
    half_diff = (cxx - cyy) / 2
    root = math.sqrt(half_diff * half_diff + cxy * cxy)
    l1 = tr / 2 + root
    l2 = max(tr / 2 - root, 0.0)
    angle = 0.5 * math.atan2(2 * cxy, cxx - cyy)
    return Ellipse(semi_major=ELLIPSE_K95 * math.sqrt(l1),
                   semi_minor=ELLIPSE_K95 * math.sqrt(l2), angle_rad=angle)
