"""קצב עדכון משוער (SPEC סעיף 4.6). הערכה בלבד."""

from __future__ import annotations

import math
from typing import Sequence

from .models import SOUND_SPEED, Buoy, ErrorParams, User

GUARD_S = 0.05  # מרווח הפרדה בין שידורים, שניות


def max_slant_range(buoys: Sequence[Buoy], users: Sequence[User], params: ErrorParams) -> float:
    dz = params.user_depth - params.transducer_depth
    return max((math.sqrt((b.x - u.x) ** 2 + (b.y - u.y) ** 2 + dz * dz)
                for b in buoys for u in users), default=0.0)


def cycle_time_s(buoys: Sequence[Buoy], users: Sequence[User], params: ErrorParams) -> float | None:
    """משך מחזור מדידה מלא בשניות. None כשאין מצופים או משתמשים."""
    if not buoys or not users:
        return None
    R = max_slant_range(buoys, users, params)
    if params.mode == "active":
        return len(users) * (2 * R / SOUND_SPEED + GUARD_S)
    return len(buoys) * (R / SOUND_SPEED + GUARD_S)


def update_rate_hz(buoys: Sequence[Buoy], users: Sequence[User], params: ErrorParams) -> float:
    """קצב עדכון למשתמש ב-Hz. 0 כשאין מצופים או משתמשים."""
    T = cycle_time_s(buoys, users, params)
    return 0.0 if not T else 1.0 / T
