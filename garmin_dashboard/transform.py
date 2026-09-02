"""Pure functions: date maths, unit formatting, and the derived chart series."""

from __future__ import annotations

import datetime as dt
import math
from collections.abc import Iterator, Sequence
from typing import TypeVar

from .cache import DayCache
from .models import Activity, SportSeries, WeeklyTotals

M_TO_MI = 1.0 / 1609.344
M_TO_KM = 1.0 / 1000.0
MPS_TO_MPH = 2.2369362920544
KG_TO_LB = 2.2046226218

T = TypeVar("T")


# --------------------------------------------------------------------------- #
# dates                                                                        #
# --------------------------------------------------------------------------- #
def daterange(start: dt.date, end: dt.date) -> Iterator[dt.date]:
    d = start
    while d <= end:
        yield d
        d += dt.timedelta(days=1)


def week_start(d: dt.date) -> dt.date:
    """Monday that begins the ISO week containing ``d``."""
    return d - dt.timedelta(days=d.weekday())


# --------------------------------------------------------------------------- #
# duration formatting                                                          #
# --------------------------------------------------------------------------- #
def hhmm(seconds: float | None) -> str:
    if not seconds:
        return "--"
    s = round(seconds)
    h, rem = divmod(s, 3600)
    m, _ = divmod(rem, 60)
    return f"{h}:{m:02d}" if h else f"{m}:{_:02d}"


def mmss(seconds: float | None) -> str:
    if not seconds or seconds <= 0 or math.isinf(seconds):
        return "--"
    s = round(seconds)
    m, sec = divmod(s, 60)
    return f"{m}:{sec:02d}"


def fmt_dur(seconds: float | None) -> str:
    """``H:MM:SS`` (or ``M:SS`` under an hour), truncated -- matches Garmin's PR display."""
    if not seconds or seconds <= 0:
        return "--"
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


# --------------------------------------------------------------------------- #
# series pulled out of the daily cache                                         #
# --------------------------------------------------------------------------- #
def series(
    cache: DayCache, start: dt.date, end: dt.date, field: str
) -> tuple[list[str], list[object]]:
    labels: list[str] = []
    vals: list[object] = []
    for d in daterange(start, end):
        key = d.isoformat()
        labels.append(key)
        vals.append(cache.get(key, field))
    return labels, vals


def carry_forward(vals: Sequence[T | None]) -> list[T | None]:
    out: list[T | None] = []
    last: T | None = None
    for v in vals:
        if v is not None:
            last = v
        out.append(last)
    return out


# --------------------------------------------------------------------------- #
# weekly volume + time                                                         #
# --------------------------------------------------------------------------- #
_SPORTS = ("run", "bike", "swim")


def weekly_totals(acts: Sequence[Activity], mileage_weeks: int, today: dt.date) -> WeeklyTotals:
    """Per-week distance and time by sport, weeks running Monday -> Sunday."""
    weeks: list[dt.date] = []
    cur = week_start(today) - dt.timedelta(weeks=mileage_weeks - 1)
    last = week_start(today)
    while cur <= last:
        weeks.append(cur)
        cur += dt.timedelta(weeks=1)
    idx = {w.isoformat(): i for i, w in enumerate(weeks)}
    n = len(weeks)

    dist: dict[str, list[float]] = {sp: [0.0] * n for sp in _SPORTS}
    time: dict[str, list[float]] = {sp: [0.0] * n for sp in _SPORTS}
    for a in acts:
        try:
            ws = week_start(dt.date.fromisoformat(a.date)).isoformat()
        except ValueError:
            continue
        i = idx.get(ws)
        if i is None:
            continue
        sp = a.sport
        dist[sp][i] += a.dist_m * (M_TO_KM if sp == "swim" else M_TO_MI)
        time[sp][i] += (a.dur_s or 0.0) / 3600.0

    dist_units = {"run": "mi", "bike": "mi", "swim": "km"}
    time_units = {"run": "h", "bike": "h", "swim": "h"}

    def pack(vals: dict[str, list[float]], units: dict[str, str]) -> dict[str, SportSeries]:
        return {
            sp: SportSeries(unit=units[sp], values=[round(x, 1) for x in vals[sp]])
            for sp in _SPORTS
        }

    return WeeklyTotals(
        labels=[w.strftime("%b %-d") for w in weeks],
        dist=pack(dist, dist_units),
        time=pack(time, time_units),
    )


# --------------------------------------------------------------------------- #
# recent-activities table                                                      #
# --------------------------------------------------------------------------- #
def recent_table(
    acts: Sequence[Activity], table_days: int, today: dt.date
) -> list[dict[str, object]]:
    cutoff = (today - dt.timedelta(days=table_days)).isoformat()
    rows: list[dict[str, object]] = []
    for a in acts:
        if a.date < cutoff:
            continue
        spd = a.speed_mps
        if a.sport == "run":
            dist_txt = f"{a.dist_m * M_TO_MI:.2f} mi"
            pace_txt = f"{mmss(1609.344 / spd)} /mi" if spd else "--"
        elif a.sport == "bike":
            dist_txt = f"{a.dist_m * M_TO_MI:.2f} mi"
            pace_txt = f"{spd * MPS_TO_MPH:.1f} mph" if spd else "--"
        else:
            dist_txt = f"{a.dist_m:.0f} m"
            pace_txt = f"{mmss(100.0 / spd)} /100m" if spd else "--"
        rows.append(
            {
                "date": a.date,
                "sport": a.sport,
                "name": a.name,
                "type": a.type_key.replace("_", " "),
                "dist": dist_txt,
                "pace": pace_txt,
                "dur": hhmm(a.dur_s),
                "hr": int(a.avg_hr) if a.avg_hr else None,
            }
        )
    rows.sort(key=lambda r: str(r["date"]), reverse=True)
    return rows
