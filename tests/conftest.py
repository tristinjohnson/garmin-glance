"""Shared fixtures: a fake Garmin client plus the frozen synthetic dataset."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

import pytest

from garmin_dashboard.cache import DayCache
from garmin_dashboard.models import Activity, Profile, Race, Settings, Windows

FIXTURES = Path(__file__).parent / "fixtures"
ANCHOR = dt.date(2026, 9, 1)


def _load(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def anchor() -> dt.date:
    return ANCHOR


@pytest.fixture
def sample_daily() -> dict[str, Any]:
    data: dict[str, Any] = _load("sample_daily.json")
    return data


@pytest.fixture
def sample_cache(tmp_path: Path, sample_daily: dict[str, Any]) -> DayCache:
    return DayCache(tmp_path / "cache.json", dict(sample_daily))


@pytest.fixture
def sample_activities() -> list[Activity]:
    return [Activity(**row) for row in _load("sample_activities.json")]


@pytest.fixture
def sample_profile() -> Profile:
    from garmin_dashboard.models import PersonalRecord

    raw = dict(_load("sample_profile.json"))
    raw["prs"] = tuple(PersonalRecord(**p) for p in raw.get("prs", []))
    return Profile(**raw)


@pytest.fixture
def settings() -> Settings:
    return Settings(
        windows=Windows(),
        races=(
            Race("Around the Crown 10K", dt.date(2026, 9, 6)),
            Race("IRONMAN 70.3 Augusta", dt.date(2026, 9, 27)),
            Race("Space Coast Marathon", dt.date(2026, 11, 22)),
        ),
        token_store="/tmp/tokens",
    )


class FakeGarmin:
    """Stand-in for :class:`garmin_dashboard.garmin_client.GarminClient`."""

    def __init__(self, **responses: Any) -> None:
        self._r = responses
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    def _get(self, name: str, *args: Any) -> Any:
        self.calls.append((name, args))
        val = self._r.get(name)
        return val(*args) if callable(val) else val

    def training_status(self, day: str) -> Any:
        return self._get("training_status", day)

    def hrv(self, day: str) -> Any:
        return self._get("hrv", day)

    def rhr(self, day: str) -> Any:
        return self._get("rhr", day)

    def sleep(self, day: str) -> Any:
        return self._get("sleep", day)

    def activities_by_date(self, start: str, end: str) -> list[dict[str, Any]]:
        return self._get("activities_by_date", start, end) or []

    def full_name(self) -> str:
        return self._get("full_name") or ""

    def user_profile(self) -> Any:
        return self._get("user_profile")

    def personal_records(self) -> Any:
        return self._get("personal_records")

    def race_predictions(self) -> Any:
        return self._get("race_predictions")

    def endurance_score(self, day: str) -> Any:
        return self._get("endurance_score", day)

    def cycling_ftp(self) -> Any:
        return self._get("cycling_ftp")

    def training_readiness(self, day: str) -> Any:
        return self._get("training_readiness", day)


@pytest.fixture
def fake_garmin() -> type[FakeGarmin]:
    return FakeGarmin
