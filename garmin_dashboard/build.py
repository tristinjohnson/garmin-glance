"""Assemble a :class:`DashboardData` from the daily cache + activities + profile.

This step is pure: given the same inputs it produces the same payload, with no
network. The CLI fills the inputs from Garmin (or, in ``--demo`` mode, from
bundled sample data).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Sequence

from .cache import DayCache
from .models import (
    Activity,
    DashboardData,
    Profile,
    RaceCountdown,
    Settings,
    Windows,
)
from .transform import carry_forward, recent_table, series, week_start, weekly_totals


def _countdowns(
    settings: Settings, today: dt.date
) -> tuple[list[RaceCountdown], RaceCountdown | None]:
    races: list[RaceCountdown] = []
    for r in settings.races:
        days = (r.date - today).days
        races.append(
            RaceCountdown(
                name=r.name,
                date=r.date.isoformat(),
                date_fmt=r.date.strftime("%a, %b %-d, %Y"),
                days=days,
                weeks=round(days / 7, 1),
                past=days < 0,
            )
        )
    upcoming = [r for r in races if not r.past]
    next_race = min(upcoming, key=lambda r: r.days) if upcoming else None
    return races, next_race


def build_dashboard(
    *,
    settings: Settings,
    cache: DayCache,
    activities: Sequence[Activity],
    profile: Profile,
    athlete: str,
    today: dt.date | None = None,
    generated: str | None = None,
) -> DashboardData:
    today = today or dt.date.today()
    win: Windows = settings.windows

    load_start = today - dt.timedelta(weeks=win.load_weeks)
    rec_start = today - dt.timedelta(weeks=win.recovery_weeks)

    l_labels, ctl = series(cache, load_start, today, "ctl")
    _, atl = series(cache, load_start, today, "atl")
    _, tsb = series(cache, load_start, today, "tsb")
    _, vo2_raw = series(cache, load_start, today, "vo2")
    vo2 = carry_forward(vo2_raw)

    r_labels, hrv_weekly = series(cache, rec_start, today, "hrv_weekly")
    _, hrv_last = series(cache, rec_start, today, "hrv_last")
    _, rhr = series(cache, rec_start, today, "rhr")
    _, sleep_h = series(cache, rec_start, today, "sleep_h")
    _, sleep_score = series(cache, rec_start, today, "sleep_score")
    _, hrv_lo = series(cache, rec_start, today, "hrv_base_low")
    _, hrv_hi = series(cache, rec_start, today, "hrv_base_high")

    d_phrase_day, d_phrase = cache.latest("ts_phrase")

    races, next_race = _countdowns(settings, today)

    return DashboardData(
        generated=generated or dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        today=today.isoformat(),
        athlete=f"/ {athlete}" if athlete else "",
        windows=win,
        races=races,
        next_race=next_race,
        profile=profile,
        snapshot={
            "ctl": cache.latest("ctl")[1],
            "atl": cache.latest("atl")[1],
            "tsb": cache.latest("tsb")[1],
            "acwr": cache.latest("acwr")[1],
            "ts_phrase": d_phrase,
            "ts_date": d_phrase_day,
            "vo2_run": cache.latest("vo2")[1],
            "vo2_bike": cache.latest("vo2_cycling")[1],
            "rhr": cache.latest("rhr")[1],
            "hrv": cache.latest("hrv_weekly")[1],
            "hrv_status": cache.latest("hrv_status")[1],
        },
        load={"labels": l_labels, "ctl": ctl, "atl": atl, "tsb": tsb},
        vo2={"labels": l_labels, "values": vo2},
        weekly=weekly_totals(activities, win.mileage_weeks, today),
        recovery={
            "labels": r_labels,
            "hrv_weekly": hrv_weekly,
            "hrv_last": hrv_last,
            "hrv_lo": carry_forward(hrv_lo),
            "hrv_hi": carry_forward(hrv_hi),
            "rhr": rhr,
            "sleep_h": sleep_h,
            "sleep_score": sleep_score,
        },
        table=recent_table(activities, win.table_days, today),
    )


__all__ = ["build_dashboard", "week_start"]
