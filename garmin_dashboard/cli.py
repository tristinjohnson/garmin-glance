"""Command-line entry point: fetch (or fake) the data, render ``index.html``."""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import sys
import webbrowser
from pathlib import Path
from typing import cast

from . import __version__
from .build import build_dashboard
from .cache import DayCache
from .config import load_settings
from .models import DashboardData, Profile
from .render import render

log = logging.getLogger("garmin_dashboard")


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="garmin-dashboard",
        description="Build a self-contained training dashboard from Garmin Connect.",
    )
    p.add_argument(
        "--config",
        type=Path,
        default=Path("config.toml"),
        help="config file (default: ./config.toml)",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=Path("index.html"),
        help="output HTML path (default: ./index.html)",
    )
    p.add_argument(
        "--cache",
        type=Path,
        default=Path(".dashboard_cache.json"),
        help="per-day cache path (default: ./.dashboard_cache.json)",
    )
    p.add_argument(
        "--demo",
        action="store_true",
        help="render from bundled synthetic data; no Garmin login",
    )
    p.add_argument(
        "--no-fetch",
        action="store_true",
        help="skip Garmin calls; render load/recovery from the existing cache "
        "(activity sections will be empty)",
    )
    p.add_argument("--open", action="store_true", help="open the result in a browser when done")
    p.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    p.add_argument("-q", "--quiet", action="store_true", help="warnings and errors only")
    p.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")
    return p


def _build_demo(config: Path) -> DashboardData:
    from .demo import generate_demo

    settings = load_settings(config)
    today = dt.date.today()
    cache, acts, profile, athlete = generate_demo(today)
    return build_dashboard(
        settings=settings,
        cache=cache,
        activities=acts,
        profile=profile,
        athlete=athlete,
        today=today,
    )


def _build_live(args: argparse.Namespace) -> DashboardData:
    from .fetchers.activities import fetch_activities
    from .fetchers.daily import DAY_STREAMS, fetch_daily
    from .fetchers.profile import fetch_profile
    from .garmin_client import GarminAuthError, GarminClient

    settings = load_settings(args.config)
    cache = DayCache.load(args.cache)
    today = dt.date.today()
    win = settings.windows

    if args.no_fetch:
        log.info("--no-fetch: rendering from the existing cache (%s)", args.cache)
        return build_dashboard(
            settings=settings,
            cache=cache,
            activities=[],
            profile=Profile(),
            athlete="",
            today=today,
        )

    try:
        client = GarminClient.login(settings.token_store)
    except GarminAuthError as exc:
        sys.exit(str(exc))

    load_start = today - dt.timedelta(weeks=win.load_weeks)
    rec_start = today - dt.timedelta(weeks=win.recovery_weeks)
    act_start = min(
        load_start,
        today - dt.timedelta(days=today.weekday()) - dt.timedelta(weeks=win.mileage_weeks - 1),
    )

    fetch_daily(
        client,
        cache,
        load_start,
        today,
        ["load"],
        refetch_recent_days=win.refetch_recent_days,
        today=today,
    )
    fetch_daily(
        client,
        cache,
        rec_start,
        today,
        [s for s in DAY_STREAMS if s != "load"],
        refetch_recent_days=win.refetch_recent_days,
        today=today,
    )
    log.info("Fetching activities ...")
    acts = fetch_activities(client, act_start, today)
    log.info("  %d run/bike/swim activities in window", len(acts))
    log.info("Fetching profile & performance numbers ...")
    profile = fetch_profile(client, today)
    athlete = client.full_name()
    cache.save()

    return build_dashboard(
        settings=settings,
        cache=cache,
        activities=acts,
        profile=profile,
        athlete=athlete,
        today=today,
    )


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    level = logging.DEBUG if args.verbose else logging.WARNING if args.quiet else logging.INFO
    logging.basicConfig(level=level, format="%(message)s", stream=sys.stderr)

    data = _build_demo(args.config) if args.demo else _build_live(args)
    html = render(data, demo=args.demo)
    args.out.write_text(html)

    ctl = cast("list[object]", data.load["ctl"])
    hrv = cast("list[object]", data.recovery["hrv_weekly"])
    n_load = sum(v is not None for v in ctl)
    n_hrv = sum(v is not None for v in hrv)
    log.info("")
    log.info("  wrote %s", args.out)
    log.info(
        "  %d activities in table · %d days of load · %d days of HRV",
        len(data.table),
        n_load,
        n_hrv,
    )

    if args.open:
        webbrowser.open(args.out.resolve().as_uri())
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
