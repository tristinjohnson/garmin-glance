"""DayCache load/save/merge and the daily fetch loop's skip logic."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

from garmin_dashboard.cache import DayCache
from garmin_dashboard.fetchers.daily import fetch_daily, parse_load, parse_sleep


def test_load_missing_file_is_empty(tmp_path: Path) -> None:
    c = DayCache.load(tmp_path / "nope.json")
    assert c.daily == {}


def test_load_rejects_garbage(tmp_path: Path) -> None:
    p = tmp_path / "c.json"
    p.write_text("not json{{")
    assert DayCache.load(p).daily == {}
    p.write_text(json.dumps({"unexpected": 1}))
    assert DayCache.load(p).daily == {}


def test_save_load_roundtrip(tmp_path: Path) -> None:
    p = tmp_path / "c.json"
    c = DayCache(p, {"2026-09-01": {"ctl": 800.0, "_have": ["load"]}})
    c.save()
    assert DayCache.load(p).daily == c.daily


def test_mark_merges_without_clobbering(tmp_path: Path) -> None:
    c = DayCache(tmp_path / "c.json")
    c.record("2026-09-01")["ctl"] = 800
    c.mark("2026-09-01", "load")
    c.mark("2026-09-01", "hrv")
    assert c.have("2026-09-01") == {"load", "hrv"}
    assert c.daily["2026-09-01"]["ctl"] == 800


def test_latest_returns_most_recent_non_null(tmp_path: Path) -> None:
    c = DayCache(
        tmp_path / "c.json",
        {
            "2026-08-30": {"ctl": 700},
            "2026-08-31": {"ctl": None},
            "2026-09-01": {"atl": 900},
        },
    )
    assert c.latest("ctl") == ("2026-08-30", 700)
    assert c.latest("missing") == (None, None)


def test_fetch_daily_skips_cached_but_refetches_recent(tmp_path: Path, fake_garmin: Any) -> None:
    today = dt.date(2026, 9, 10)
    cache = DayCache(
        tmp_path / "c.json",
        {
            "2026-09-01": {"ctl": 1, "_have": ["load"]},  # old + cached -> skip
            "2026-09-09": {"ctl": 2, "_have": ["load"]},  # within refetch window -> refetch
        },
    )
    ts_payload = {
        "mostRecentTrainingStatus": {
            "latestTrainingStatusData": {
                "dev": {
                    "primaryTrainingDevice": True,
                    "acuteTrainingLoadDTO": {
                        "dailyTrainingLoadAcute": 810,
                        "dailyTrainingLoadChronic": 830,
                    },
                }
            }
        }
    }
    client = fake_garmin(training_status=ts_payload)
    fetch_daily(
        client,
        cache,
        dt.date(2026, 9, 8),
        today,
        ["load"],
        refetch_recent_days=3,
        today=today,
    )

    fetched_days = {args[0] for name, args in client.calls if name == "training_status"}
    assert "2026-09-01" not in fetched_days  # untouched
    assert "2026-09-09" in fetched_days and "2026-09-10" in fetched_days
    assert cache.daily["2026-09-09"]["ctl"] == 830.0  # overwritten from payload


def test_parse_load_reads_acute_chronic() -> None:
    out = parse_load(
        {
            "mostRecentTrainingStatus": {
                "latestTrainingStatusData": {
                    "d": {
                        "acuteTrainingLoadDTO": {
                            "dailyTrainingLoadAcute": 800,
                            "dailyTrainingLoadChronic": 850,
                            "dailyAcuteChronicWorkloadRatio": 0.94,
                        },
                        "trainingStatusFeedbackPhrase": "MAINTAINING_2",
                    }
                }
            },
            "mostRecentVO2Max": {"generic": {"vo2MaxPreciseValue": 57.3}},
        }
    )
    assert out["atl"] == 800.0 and out["ctl"] == 850.0 and out["tsb"] == 50.0
    assert out["acwr"] == 0.94 and out["vo2"] == 57.3


def test_parse_load_tolerates_empty() -> None:
    out = parse_load(None)
    assert out["ctl"] is None and out["tsb"] is None


def test_parse_sleep_converts_seconds() -> None:
    out = parse_sleep(
        {"dailySleepDTO": {"sleepTimeSeconds": 27000, "sleepScores": {"overall": {"value": 82}}}}
    )
    assert out["sleep_h"] == 7.5 and out["sleep_score"] == 82
