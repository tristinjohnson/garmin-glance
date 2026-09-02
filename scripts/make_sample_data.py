#!/usr/bin/env python
"""Regenerate the frozen demo fixtures used by the tests.

``--demo`` mode generates its data live (anchored to today), so this script is
only needed to refresh ``tests/fixtures/`` and the screenshot source. Run:

    uv run python scripts/make_sample_data.py
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from garmin_dashboard.build import build_dashboard  # noqa: E402
from garmin_dashboard.config import load_settings  # noqa: E402
from garmin_dashboard.demo import generate_demo  # noqa: E402
from garmin_dashboard.render import render  # noqa: E402

ANCHOR = dt.date(2026, 9, 1)  # fixed so fixtures are stable
FIXTURES = ROOT / "tests" / "fixtures"


def main() -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    settings = load_settings(ROOT / "config.toml")
    cache, acts, profile, _athlete = generate_demo(ANCHOR)

    (FIXTURES / "sample_daily.json").write_text(json.dumps(cache.daily, indent=2, sort_keys=True))
    (FIXTURES / "sample_activities.json").write_text(
        json.dumps([asdict(a) for a in acts], indent=2)
    )
    (FIXTURES / "sample_profile.json").write_text(json.dumps(asdict(profile), indent=2))

    data = build_dashboard(
        settings=settings,
        cache=cache,
        activities=acts,
        profile=profile,
        athlete="Sample Athlete",
        today=ANCHOR,
        generated="2026-09-01 08:00",
    )
    (FIXTURES / "sample_payload.json").write_text(
        json.dumps(data.as_payload(), indent=2, sort_keys=True)
    )

    # A rendered copy for regenerating the README screenshots (dist/ is gitignored).
    dist = ROOT / "dist"
    dist.mkdir(exist_ok=True)
    (dist / "demo.html").write_text(render(data, demo=True))
    print(f"wrote fixtures to {FIXTURES}\nwrote {dist / 'demo.html'}")


if __name__ == "__main__":
    main()
