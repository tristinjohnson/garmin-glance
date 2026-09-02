"""End-to-end build + render: shape, no placeholder leaks, HTML escaping."""

from __future__ import annotations

import datetime as dt
import json
import re
from typing import Any

from garmin_dashboard.build import build_dashboard
from garmin_dashboard.cache import DayCache
from garmin_dashboard.models import Activity, Profile
from garmin_dashboard.render import render


def _build(cache: DayCache, settings: Any, acts: Any, profile: Profile, today: dt.date) -> Any:
    return build_dashboard(
        settings=settings,
        cache=cache,
        activities=acts,
        profile=profile,
        athlete="Sample Athlete",
        today=today,
        generated="2026-09-01 08:00",
    )


def test_payload_shape(sample_cache, settings, sample_activities, sample_profile, anchor) -> None:
    data = _build(sample_cache, settings, sample_activities, sample_profile, anchor)
    payload = data.as_payload()

    assert set(payload) >= {
        "generated",
        "today",
        "athlete",
        "windows",
        "races",
        "next_race",
        "profile",
        "snapshot",
        "load",
        "vo2",
        "weekly",
        "recovery",
        "table",
    }
    assert payload["athlete"] == "/ Sample Athlete"
    assert payload["weekly"]["dist"]["swim"]["unit"] == "km"
    assert len(payload["load"]["labels"]) == len(payload["load"]["ctl"])
    # next race is the soonest future one
    assert payload["next_race"]["name"] == "Around the Crown 10K"
    assert payload["snapshot"]["ctl"] is not None


def test_matches_frozen_payload(
    sample_cache, settings, sample_activities, sample_profile, anchor
) -> None:
    data = _build(sample_cache, settings, sample_activities, sample_profile, anchor)
    frozen = json.loads(
        (
            __import__("pathlib").Path(__file__).parent / "fixtures" / "sample_payload.json"
        ).read_text()
    )
    assert json.loads(json.dumps(data.as_payload())) == frozen


def test_render_has_no_unfilled_placeholders(
    sample_cache, settings, sample_activities, sample_profile, anchor
) -> None:
    html = render(_build(sample_cache, settings, sample_activities, sample_profile, anchor))
    assert "{{" not in html and "{%" not in html
    assert not re.search(r"__[A-Z_]+__", html)
    assert '<canvas id="loadChart">' in html
    assert "const DATA = {" in html


def test_demo_banner_only_in_demo_mode(
    sample_cache, settings, sample_activities, sample_profile, anchor
) -> None:
    data = _build(sample_cache, settings, sample_activities, sample_profile, anchor)
    assert "Demo data &mdash;" not in render(data, demo=False)
    assert "Demo data &mdash;" in render(data, demo=True)


def test_activity_name_is_escaped(sample_cache, settings, sample_profile, anchor) -> None:
    evil = Activity(
        id=1,
        date="2026-08-30",
        start="2026-08-30 06:00:00",
        name="</script><script>alert(1)</script>",
        sport="run",
        type_key="running",
        dist_m=5000,
        dur_s=1500,
        moving_s=1500,
        avg_hr=140,
        max_hr=170,
        speed_mps=3.3,
        elev_gain_m=0,
    )
    html = render(_build(sample_cache, settings, [evil], sample_profile, anchor))
    assert "<script>alert(1)</script>" not in html
    assert "\\u003c/script\\u003e" in html or "\\u003cscript\\u003e" in html
