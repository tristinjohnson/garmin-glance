"""Typed data structures passed between the fetch, transform and render stages."""

from __future__ import annotations

import datetime as dt
from dataclasses import asdict, dataclass, field

Sport = str  # one of "run", "bike", "swim"


# --------------------------------------------------------------------------- #
# configuration                                                                #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class Windows:
    """How far back each section of the dashboard looks."""

    load_weeks: int = 12
    recovery_weeks: int = 6
    mileage_weeks: int = 12
    table_days: int = 28
    refetch_recent_days: int = 3


@dataclass(frozen=True, slots=True)
class Race:
    name: str
    date: dt.date


@dataclass(frozen=True, slots=True)
class Settings:
    windows: Windows
    races: tuple[Race, ...]
    token_store: str


# --------------------------------------------------------------------------- #
# fetched primitives                                                           #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class Activity:
    """One normalised run / bike / swim."""

    id: int | None
    date: str  # YYYY-MM-DD (local)
    start: str
    name: str
    sport: Sport
    type_key: str
    dist_m: float
    dur_s: float
    moving_s: float
    avg_hr: float | None
    max_hr: float | None
    speed_mps: float
    elev_gain_m: float | None


@dataclass(frozen=True, slots=True)
class PersonalRecord:
    label: str
    value: str
    grp: str  # "run" or "tri"


@dataclass(frozen=True, slots=True)
class Profile:
    height_cm: float | None = None
    weight_kg: float | None = None
    vo2_run: float | None = None
    vo2_bike: float | None = None
    lthr: int | None = None
    prs: tuple[PersonalRecord, ...] = ()
    predictions: dict[str, str] = field(default_factory=dict)
    endurance: float | None = None
    endurance_class: str | None = None
    ftp: float | None = None
    readiness: float | None = None
    readiness_level: str | None = None


# --------------------------------------------------------------------------- #
# assembled dashboard payload                                                  #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class RaceCountdown:
    name: str
    date: str
    date_fmt: str
    days: int
    weeks: float
    past: bool


@dataclass(frozen=True, slots=True)
class SportSeries:
    unit: str
    values: list[float]


@dataclass(frozen=True, slots=True)
class WeeklyTotals:
    labels: list[str]
    dist: dict[Sport, SportSeries]
    time: dict[Sport, SportSeries]


@dataclass(frozen=True, slots=True)
class DashboardData:
    """Everything the template needs. ``as_payload`` is the JSON handed to the page."""

    generated: str
    today: str
    athlete: str
    windows: Windows
    races: list[RaceCountdown]
    next_race: RaceCountdown | None
    profile: Profile
    snapshot: dict[str, object]
    load: dict[str, object]
    vo2: dict[str, object]
    weekly: WeeklyTotals
    recovery: dict[str, object]
    table: list[dict[str, object]]

    def as_payload(self) -> dict[str, object]:
        """Plain dict in the exact shape ``dashboard.js`` consumes."""

        def series(s: SportSeries) -> dict[str, object]:
            return {"unit": s.unit, "values": s.values}

        return {
            "generated": self.generated,
            "today": self.today,
            "athlete": self.athlete,
            "windows": {
                "load": self.windows.load_weeks,
                "recovery": self.windows.recovery_weeks,
                "mileage": self.windows.mileage_weeks,
                "table": self.windows.table_days,
            },
            "races": [asdict(r) for r in self.races],
            "next_race": asdict(self.next_race) if self.next_race else None,
            "profile": {
                "height_cm": self.profile.height_cm,
                "weight_kg": self.profile.weight_kg,
                "vo2_run": self.profile.vo2_run,
                "vo2_bike": self.profile.vo2_bike,
                "lthr": self.profile.lthr,
                "prs": [asdict(p) for p in self.profile.prs],
                "predictions": self.profile.predictions,
                "endurance": self.profile.endurance,
                "endurance_class": self.profile.endurance_class,
                "ftp": self.profile.ftp,
                "readiness": self.profile.readiness,
                "readiness_level": self.profile.readiness_level,
            },
            "snapshot": self.snapshot,
            "load": self.load,
            "vo2": self.vo2,
            "weekly": {
                "labels": self.weekly.labels,
                "dist": {k: series(v) for k, v in self.weekly.dist.items()},
                "time": {k: series(v) for k, v in self.weekly.time.items()},
            },
            "recovery": self.recovery,
            "table": self.table,
        }
