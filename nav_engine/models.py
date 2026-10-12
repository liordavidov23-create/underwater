"""מבני נתונים של המודל (SPEC סעיפים 4.1, 5, 9).

מערכת קואורדינטות מקומית במטרים: x מזרחה, y צפונה, עומק חיובי כלפי מטה.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

SOUND_SPEED = 1500.0  # מטר לשנייה
MODES = ("sync", "unsync", "active")

# פריסות ייחוס (SPEC סעיף 5)
REFERENCE_LAYOUTS: dict[str, list[tuple[float, float]]] = {
    "around": [(60, 35), (275, 40), (270, 205), (65, 200)],
    "west": [(60, 30), (40, 95), (40, 155), (60, 215)],
    "chal": [(55, 90), (55, 120), (55, 150)],
    "solve": [(65, 2), (65, 60), (65, 120), (65, 180), (65, 238)],
}

# משתמשים ברירת מחדל (SPEC סעיף 5)
DEFAULT_USERS: list[tuple[str, str, float, float]] = [
    ("D1", "diver", 145, 160),
    ("D2", "diver", 175, 95),
    ("D3", "diver", 193, 152),
    ("R1", "robot", 153, 120),
    ("R2", "robot", 197, 75),
]


@dataclass
class Buoy:
    x: float
    y: float
    name: str = ""


@dataclass
class User:
    id: str
    x: float
    y: float
    kind: str = "diver"  # diver או robot


@dataclass
class ErrorParams:
    """פרמטרי השגיאה. כולם הנחות טיפוסיות, לא נתוני יצרן."""

    sigma_range: float = 0.3        # מטר
    sound_speed_frac: float = 0.002  # שבר (0.2%)
    sigma_gnss: float = 0.5         # מטר
    sigma_clock: float = 200e-6     # שניות
    user_depth: float = 15.0        # מטר
    transducer_depth: float = 2.0   # מטר
    mode: str = "sync"              # sync, unsync, active

    def __post_init__(self) -> None:
        if self.mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}, got {self.mode!r}")


@dataclass
class WorkArea:
    x0: float = 70.0
    y0: float = 45.0
    x1: float = 270.0
    y1: float = 195.0


@dataclass
class Scenario:
    buoys: list[Buoy]
    users: list[User]
    params: ErrorParams = field(default_factory=ErrorParams)
    area: WorkArea = field(default_factory=WorkArea)
    strip_x_max: float = 65.0   # רצועת פריסה מותרת: x <= ערך זה
    world_w: float = 280.0
    world_h: float = 240.0
    name: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Scenario":
        return cls(
            buoys=[Buoy(**b) for b in d.get("buoys", [])],
            users=[User(**u) for u in d.get("users", [])],
            params=ErrorParams(**d.get("params", {})),
            area=WorkArea(**d.get("area", {})),
            strip_x_max=d.get("strip_x_max", 65.0),
            world_w=d.get("world_w", 280.0),
            world_h=d.get("world_h", 240.0),
            name=d.get("name", ""),
        )


@dataclass
class EquipmentParam:
    """ערך בודד בספריית הציוד. ערך בלי מקור הוא "הנחה" עם ביטחון נמוך."""

    value: float | None
    source: str = ""
    confidence: str = "נמוכה"  # גבוהה, בינונית, נמוכה
    note: str = ""


@dataclass
class Equipment:
    id: str
    name: str
    kind: str  # component או system
    params: dict[str, EquipmentParam] = field(default_factory=dict)


def default_users() -> list[User]:
    return [User(id=i, kind=k, x=x, y=y) for i, k, x, y in DEFAULT_USERS]


def reference_buoys(name: str) -> list[Buoy]:
    return [Buoy(x=x, y=y, name=f"B{i + 1}") for i, (x, y) in enumerate(REFERENCE_LAYOUTS[name])]


def default_scenario(layout: str = "west") -> Scenario:
    return Scenario(buoys=reference_buoys(layout), users=default_users(), name=layout)
