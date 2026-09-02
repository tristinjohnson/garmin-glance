"""Fetch the run / bike / swim activities in a date window and normalise them."""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any

from ..garmin_client import GarminClient
from ..models import Activity

log = logging.getLogger(__name__)

RUN_TYPES = {
    "running",
    "trail_running",
    "treadmill_running",
    "track_running",
    "virtual_run",
    "indoor_running",
    "obstacle_run",
    "ultra_run",
}
BIKE_TYPES = {
    "cycling",
    "road_biking",
    "mountain_biking",
    "gravel_cycling",
    "virtual_ride",
    "indoor_cycling",
    "cyclocross",
    "track_cycling",
    "bmx",
    "e_bike_fitness",
    "e_bike_mountain",
    "downhill_biking",
    "recumbent_cycling",
}
SWIM_TYPES = {"lap_swimming", "open_water_swimming", "swimming"}


def sport_of(type_key: str) -> str | None:
    if type_key in RUN_TYPES:
        return "run"
    if type_key in BIKE_TYPES:
        return "bike"
    if type_key in SWIM_TYPES:
        return "swim"
    return None


def normalise(raw: dict[str, Any]) -> Activity | None:
    """One raw activity dict -> :class:`Activity`, or ``None`` if not run/bike/swim."""
    type_key = ((raw.get("activityType") or {}).get("typeKey")) or ""
    if type_key == "multi_sport":
        return None  # children are listed separately; avoid double-counting
    sport = sport_of(type_key)
    if sport is None:
        return None

    started = raw.get("startTimeLocal") or raw.get("startTimeGMT") or ""
    dist = float(raw.get("distance") or 0.0)
    dur = float(raw.get("duration") or raw.get("elapsedDuration") or 0.0)
    moving = float(raw.get("movingDuration") or dur or 0.0)
    speed = raw.get("averageSpeed")
    if not speed and dist and moving:
        speed = dist / moving

    return Activity(
        id=raw.get("activityId"),
        date=started[:10],
        start=started,
        name=raw.get("activityName") or type_key.replace("_", " ").title(),
        sport=sport,
        type_key=type_key,
        dist_m=dist,
        dur_s=dur,
        moving_s=moving,
        avg_hr=raw.get("averageHR"),
        max_hr=raw.get("maxHR"),
        speed_mps=float(speed or 0.0),
        elev_gain_m=raw.get("elevationGain"),
    )


def fetch_activities(client: GarminClient, start: dt.date, end: dt.date) -> list[Activity]:
    raw = client.activities_by_date(start.isoformat(), end.isoformat())
    out = [act for item in raw if (act := normalise(item)) is not None]
    out.sort(key=lambda a: a.start)
    return out
