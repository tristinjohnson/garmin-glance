"""Per-day metrics: training load / VO2, HRV, resting HR, sleep.

Each ``parse_*`` function is pure -- raw Garmin dict in, flat ``{field: value}``
out -- so it can be tested against a captured payload with no network.
"""

from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Callable, Sequence
from typing import Any

from ..cache import DayCache
from ..garmin_client import GarminClient
from ..transform import daterange

log = logging.getLogger(__name__)

DAY_STREAMS: tuple[str, ...] = ("load", "hrv", "rhr", "sleep")


def _num(v: Any) -> float | None:
    return float(v) if isinstance(v, (int, float)) else None


def _d(v: Any) -> dict[str, Any]:
    return v if isinstance(v, dict) else {}


def parse_load(raw: Any) -> dict[str, Any]:
    ts = _d(raw)
    recent = _d(ts.get("mostRecentTrainingStatus"))
    latest = _d(recent.get("latestTrainingStatusData"))
    sd: dict[str, Any] = {}
    for dev in latest.values():
        if isinstance(dev, dict):
            sd = dev
            if dev.get("primaryTrainingDevice"):
                break
    atl_dto = _d(sd.get("acuteTrainingLoadDTO"))
    acute = _num(atl_dto.get("dailyTrainingLoadAcute"))
    chronic = _num(atl_dto.get("dailyTrainingLoadChronic"))
    acwr = _num(atl_dto.get("dailyAcuteChronicWorkloadRatio"))
    vo2 = _d(ts.get("mostRecentVO2Max"))
    gen = _d(vo2.get("generic"))
    cyc = _d(vo2.get("cycling"))
    return {
        "atl": round(acute, 1) if acute is not None else None,
        "ctl": round(chronic, 1) if chronic is not None else None,
        "tsb": (round(chronic - acute, 1) if acute is not None and chronic is not None else None),
        "acwr": round(acwr, 2) if acwr is not None else None,
        "acwr_status": atl_dto.get("acwrStatus"),
        "ts_phrase": sd.get("trainingStatusFeedbackPhrase"),
        "vo2": gen.get("vo2MaxPreciseValue") or gen.get("vo2MaxValue"),
        "vo2_cycling": cyc.get("vo2MaxPreciseValue") or cyc.get("vo2MaxValue"),
    }


def parse_hrv(raw: Any) -> dict[str, Any]:
    s = _d(_d(raw).get("hrvSummary"))
    base = _d(s.get("baseline"))
    return {
        "hrv_weekly": s.get("weeklyAvg"),
        "hrv_last": s.get("lastNightAvg"),
        "hrv_status": s.get("status"),
        "hrv_base_low": base.get("balancedLow"),
        "hrv_base_high": base.get("balancedUpper"),
    }


def parse_rhr(raw: Any) -> dict[str, Any]:
    metrics = _d(_d(_d(raw).get("allMetrics")).get("metricsMap")).get("WELLNESS_RESTING_HEART_RATE")
    first = metrics[0] if isinstance(metrics, list) and metrics else None
    val = first.get("value") if isinstance(first, dict) else None
    return {"rhr": val}


def parse_sleep(raw: Any) -> dict[str, Any]:
    dto = _d(_d(raw).get("dailySleepDTO"))
    sec = dto.get("sleepTimeSeconds") or 0
    overall = _d(_d(dto.get("sleepScores")).get("overall"))
    return {
        "sleep_h": round(sec / 3600, 2) if sec else None,
        "deep_h": round((dto.get("deepSleepSeconds") or 0) / 3600, 2),
        "light_h": round((dto.get("lightSleepSeconds") or 0) / 3600, 2),
        "rem_h": round((dto.get("remSleepSeconds") or 0) / 3600, 2),
        "awake_h": round((dto.get("awakeSleepSeconds") or 0) / 3600, 2),
        "sleep_score": overall.get("value"),
    }


# (raw-getter name on GarminClient, parser)
_STREAMS: dict[str, tuple[str, Callable[[Any], dict[str, Any]]]] = {
    "load": ("training_status", parse_load),
    "hrv": ("hrv", parse_hrv),
    "rhr": ("rhr", parse_rhr),
    "sleep": ("sleep", parse_sleep),
}


def fetch_daily(
    client: GarminClient,
    cache: DayCache,
    start: dt.date,
    end: dt.date,
    streams: Sequence[str],
    *,
    refetch_recent_days: int,
    today: dt.date,
) -> None:
    """Populate ``cache`` for ``[start, end]``, skipping days already fetched."""
    todo: list[tuple[str, list[str]]] = []
    for d in daterange(start, end):
        key = d.isoformat()
        have = cache.have(key)
        need = [s for s in streams if s not in have]
        if (today - d).days <= refetch_recent_days:
            need = list(streams)
        if need:
            todo.append((key, need))

    if not todo:
        return
    log.info("Fetching %d day(s) x %d stream(s) from Garmin ...", len(todo), len(streams))
    for i, (key, need) in enumerate(todo, 1):
        rec = cache.record(key)
        for stream in need:
            getter, parser = _STREAMS[stream]
            try:
                rec.update(parser(getattr(client, getter)(key)))
                cache.mark(key, stream)
            except Exception as exc:
                log.warning("  %s/%s: %s", key, stream, exc)
        if i % 20 == 0:
            log.info("  ... %d/%d", i, len(todo))
            cache.save()
    cache.save()
