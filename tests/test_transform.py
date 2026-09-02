"""Date maths, unit formatting, and the weekly / table derivations."""

from __future__ import annotations

import datetime as dt
import math

import pytest

from garmin_dashboard.models import Activity
from garmin_dashboard.transform import (
    carry_forward,
    fmt_dur,
    hhmm,
    mmss,
    recent_table,
    week_start,
    weekly_totals,
)


@pytest.mark.parametrize(
    "day,expected",
    [
        (dt.date(2026, 9, 2), dt.date(2026, 8, 31)),  # Wed -> Mon
        (dt.date(2026, 8, 31), dt.date(2026, 8, 31)),  # Mon -> itself
        (dt.date(2026, 9, 6), dt.date(2026, 8, 31)),  # Sun -> that Mon
    ],
)
def test_week_start_is_monday(day: dt.date, expected: dt.date) -> None:
    assert week_start(day) == expected
    assert week_start(day).weekday() == 0


@pytest.mark.parametrize(
    "secs,expected",
    [(None, "--"), (0, "--"), (-5, "--"), (59, "0:59"), (95, "1:35"), (3661, "1:01:01")],
)
def test_fmt_dur_truncates(secs: float | None, expected: str) -> None:
    assert fmt_dur(secs) == expected


def test_fmt_dur_does_not_round_up() -> None:
    assert fmt_dur(371.9) == "6:11"  # not 6:12


def test_mmss_and_hhmm_guard_bad_input() -> None:
    assert mmss(math.inf) == "--"
    assert mmss(0) == "--"
    assert hhmm(None) == "--"
    assert hhmm(3600) == "1:00"
    assert mmss(65) == "1:05"


def test_carry_forward_fills_gaps() -> None:
    assert carry_forward([None, 1, None, None, 3, None]) == [None, 1, 1, 1, 3, 3]


def _act(date: str, sport: str, dist_m: float, dur_s: float, speed: float = 3.0) -> Activity:
    return Activity(
        id=1,
        date=date,
        start=f"{date} 06:00:00",
        name="x",
        sport=sport,
        type_key={"run": "running", "bike": "cycling", "swim": "lap_swimming"}[sport],
        dist_m=dist_m,
        dur_s=dur_s,
        moving_s=dur_s,
        avg_hr=140,
        max_hr=170,
        speed_mps=speed,
        elev_gain_m=0,
    )


def test_weekly_totals_buckets_monday_to_sunday() -> None:
    today = dt.date(2026, 9, 2)  # Wednesday
    acts = [
        _act("2026-09-01", "run", 1609.344 * 3, 1800),  # Tue -> current week
        _act("2026-08-31", "run", 1609.344 * 5, 3000),  # Mon -> current week
        _act("2026-08-30", "run", 1609.344 * 7, 4200),  # Sun -> previous week
        _act("2026-09-02", "swim", 2000, 2400),  # Wed, swim -> km
    ]
    wt = weekly_totals(acts, mileage_weeks=12, today=today)

    assert len(wt.labels) == 12
    assert wt.dist["run"].unit == "mi" and wt.dist["swim"].unit == "km"
    assert wt.dist["run"].values[-1] == pytest.approx(8.0)  # Mon+Tue this week
    assert wt.dist["run"].values[-2] == pytest.approx(7.0)  # Sun last week
    assert wt.dist["swim"].values[-1] == pytest.approx(2.0)  # 2000 m -> 2.0 km
    assert wt.time["run"].values[-1] == pytest.approx((1800 + 3000) / 3600, abs=0.05)


def test_recent_table_windows_and_formats() -> None:
    today = dt.date(2026, 9, 2)
    acts = [
        _act("2026-09-01", "run", 1609.344, 372, speed=1609.344 / 372),
        _act("2026-07-01", "run", 1609.344, 372),  # outside 28-day window
        _act("2026-08-20", "bike", 16093.44, 1800, speed=16093.44 / 1800),
        _act("2026-08-25", "swim", 1000, 1200, speed=1000 / 1200),
    ]
    rows = recent_table(acts, table_days=28, today=today)

    assert [r["date"] for r in rows] == ["2026-09-01", "2026-08-25", "2026-08-20"]
    run_row = rows[0]
    assert run_row["dist"] == "1.00 mi"
    assert str(run_row["pace"]).endswith("/mi")
    bike_row = next(r for r in rows if r["sport"] == "bike")
    assert str(bike_row["pace"]).endswith("mph")
    swim_row = next(r for r in rows if r["sport"] == "swim")
    assert str(swim_row["pace"]).endswith("/100m")
    assert str(swim_row["dist"]).endswith(" m")
