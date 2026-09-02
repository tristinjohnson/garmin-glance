"""Sport classification, multisport exclusion, speed fallback."""

from __future__ import annotations

import datetime as dt
from typing import Any

from garmin_dashboard.fetchers.activities import fetch_activities, normalise, sport_of


def test_sport_of_maps_known_keys() -> None:
    assert sport_of("trail_running") == "run"
    assert sport_of("gravel_cycling") == "bike"
    assert sport_of("open_water_swimming") == "swim"
    assert sport_of("strength_training") is None


def test_normalise_skips_multisport_parent() -> None:
    assert normalise({"activityType": {"typeKey": "multi_sport"}, "distance": 1000}) is None


def test_normalise_skips_non_endurance() -> None:
    assert normalise({"activityType": {"typeKey": "yoga"}}) is None


def test_normalise_derives_speed_when_missing() -> None:
    act = normalise(
        {
            "activityId": 7,
            "activityType": {"typeKey": "running"},
            "startTimeLocal": "2026-09-01 06:30:00",
            "distance": 10000.0,
            "duration": 3000.0,
            "movingDuration": 2500.0,
        }
    )
    assert act is not None
    assert act.sport == "run"
    assert act.date == "2026-09-01"
    assert act.speed_mps == 10000.0 / 2500.0  # distance / movingDuration


def test_normalise_keeps_reported_speed() -> None:
    act = normalise(
        {
            "activityType": {"typeKey": "cycling"},
            "startTimeGMT": "2026-09-01 06:30:00",
            "distance": 20000.0,
            "duration": 3600.0,
            "averageSpeed": 6.5,
        }
    )
    assert act is not None and act.speed_mps == 6.5


def test_fetch_activities_sorted_and_filtered(fake_garmin: Any) -> None:
    raw = [
        {
            "activityType": {"typeKey": "running"},
            "startTimeLocal": "2026-09-02 06:00:00",
            "distance": 5000,
            "duration": 1500,
        },
        {
            "activityType": {"typeKey": "multi_sport"},
            "startTimeLocal": "2026-09-01 06:00:00",
            "distance": 9000,
            "duration": 3000,
        },
        {
            "activityType": {"typeKey": "lap_swimming"},
            "startTimeLocal": "2026-09-01 06:00:00",
            "distance": 2000,
            "duration": 2400,
        },
        {"activityType": {"typeKey": "yoga"}, "startTimeLocal": "2026-09-01 07:00:00"},
    ]
    client = fake_garmin(activities_by_date=raw)
    out = fetch_activities(client, dt.date(2026, 9, 1), dt.date(2026, 9, 2))

    assert [a.sport for a in out] == ["swim", "run"]  # sorted by start, multisport/yoga dropped
