"""Build a full, self-consistent synthetic dataset anchored to a given date.

Everything is seeded, so ``--demo`` and the test fixtures are reproducible, and
the series always line up with the current date's dashboard windows.
"""

from __future__ import annotations

import datetime as dt
import math
import random
from pathlib import Path

from ..cache import DayCache
from ..models import Activity, PersonalRecord, Profile

_ATHLETE = "Demo Athlete"
_DAYS_BACK = 7 * 14  # a little more than the widest window


def _daily(today: dt.date, rng: random.Random) -> dict[str, dict[str, object]]:
    daily: dict[str, dict[str, object]] = {}
    for i in range(_DAYS_BACK, -1, -1):
        day = (today - dt.timedelta(days=i)).isoformat()
        prog = (_DAYS_BACK - i) / _DAYS_BACK  # 0 -> 1 over the window

        ctl = 720 + 140 * prog + rng.uniform(-8, 8)
        atl = ctl + 60 * math.sin(i / 5.0) + rng.uniform(-25, 25)
        rec: dict[str, object] = {
            "ctl": round(ctl, 1),
            "atl": round(atl, 1),
            "tsb": round(ctl - atl, 1),
            "acwr": round(max(0.6, min(1.5, atl / ctl)), 2),
            "acwr_status": "OPTIMAL",
            "ts_phrase": "MAINTAINING_2",
            "vo2": round(54.5 + 3.5 * prog, 1),
            "vo2_cycling": round(56.0 + 3.0 * prog, 1),
            "_have": ["load"],
        }
        # recovery streams only for the last ~6 weeks
        if i <= 7 * 6:
            rec.update(
                hrv_weekly=round(70 + 6 * math.sin(i / 9.0) + rng.uniform(-2, 2), 0),
                hrv_last=round(70 + 10 * math.sin(i / 4.0) + rng.uniform(-6, 6), 0),
                hrv_status="BALANCED",
                hrv_base_low=58,
                hrv_base_high=82,
                rhr=round(44 + 2 * math.sin(i / 8.0) + rng.uniform(-1.5, 1.5)),
                sleep_h=round(7.4 + rng.uniform(-1.1, 1.1), 2),
                sleep_score=round(78 + rng.uniform(-16, 16)),
            )
            rec["_have"] = ["hrv", "load", "rhr", "sleep"]
        daily[day] = rec
    return daily


def _activities(today: dt.date, rng: random.Random) -> list[Activity]:
    out: list[Activity] = []
    plan = [
        ("run", 4, (6_000, 16_000), 3.1),  # sport, per week, dist range (m), m/s
        ("bike", 3, (25_000, 70_000), 8.3),
        ("swim", 2, (1_500, 3_500), 0.95),
    ]
    for week in range(13):
        monday = today - dt.timedelta(days=today.weekday()) - dt.timedelta(weeks=week)
        for sport, n, (lo, hi), base_spd in plan:
            for k in range(n):
                day = monday + dt.timedelta(days=rng.randint(0, 6))
                if day > today:
                    continue
                dist = rng.uniform(lo, hi)
                spd = base_spd * rng.uniform(0.9, 1.12)
                dur = dist / spd
                out.append(
                    Activity(
                        id=int(day.strftime("%Y%m%d")) * 10 + k,
                        date=day.isoformat(),
                        start=f"{day.isoformat()} 06:{30 + k:02d}:00",
                        name={"run": "Easy Run", "bike": "Endurance Ride", "swim": "Pool Swim"}[
                            sport
                        ],
                        sport=sport,
                        type_key={"run": "running", "bike": "cycling", "swim": "lap_swimming"}[
                            sport
                        ],
                        dist_m=round(dist, 1),
                        dur_s=round(dur, 1),
                        moving_s=round(dur, 1),
                        avg_hr=round(rng.uniform(128, 158)),
                        max_hr=round(rng.uniform(162, 182)),
                        speed_mps=round(spd, 3),
                        elev_gain_m=round(rng.uniform(0, 400)),
                    )
                )
    out.sort(key=lambda a: a.start)
    return out


def _profile() -> Profile:
    return Profile(
        height_cm=178.0,
        weight_kg=70.5,
        vo2_run=58.0,
        vo2_bike=59.0,
        lthr=168,
        prs=(
            PersonalRecord("1 mile", "5:38", "run"),
            PersonalRecord("5K", "18:42", "run"),
            PersonalRecord("10K", "39:10", "run"),
            PersonalRecord("Half Marathon", "1:27:44", "run"),
            PersonalRecord("Marathon", "3:07:59", "run"),
            PersonalRecord("400 m swim", "6:41", "tri"),
            PersonalRecord("1500 m swim", "27:10", "tri"),
        ),
        predictions={"5K": "18:30", "10K": "38:40", "Half": "1:26:10", "Marathon": "3:03:20"},
        endurance=7180,
        endurance_class="Expert",
        ftp=252.0,
        readiness=74,
        readiness_level="READY",
    )


def generate_demo(
    today: dt.date, *, seed: int = 42
) -> tuple[DayCache, list[Activity], Profile, str]:
    rng = random.Random(seed)
    cache = DayCache(Path("demo-cache.json"), _daily(today, rng))
    return cache, _activities(today, rng), _profile(), _ATHLETE
