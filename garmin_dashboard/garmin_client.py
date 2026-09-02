"""Thin wrapper around :mod:`garminconnect` -- the only module that imports it.

Auth is token-only: it resumes the OAuth tokens already cached at
``token_store`` (written by ``garmin-mcp-auth``) and never prompts for a
password. Every getter returns the raw Garmin response; parsing lives in the
``fetchers`` package so it can be unit-tested without a network.
"""

from __future__ import annotations

import time
from typing import Any


class GarminAuthError(RuntimeError):
    """Cached tokens are missing, expired or rejected."""


class GarminClient:
    def __init__(self, api: Any) -> None:
        self._api = api

    # -- construction ----------------------------------------------------- #
    @classmethod
    def login(cls, token_store: str) -> GarminClient:
        try:
            from garminconnect import Garmin
        except ImportError as exc:  # pragma: no cover - env-specific
            raise GarminAuthError(
                "The `garminconnect` package is not installed.\n"
                "  Run with uv:   uv run garmin-dashboard\n"
                "  Or install:    pip install 'garminconnect==0.3.2'"
            ) from exc

        api = Garmin()
        try:
            api.login(token_store)
        except Exception as exc:
            raise GarminAuthError(
                f"Garmin login with cached tokens failed ({token_store}): {exc}\n"
                "Refresh them with:\n"
                "  uvx --python 3.12 --from git+https://github.com/Taxuspt/garmin_mcp "
                "garmin-mcp-auth"
            ) from exc
        return cls(api)

    # -- retry helper --------------------------------------------------------- #
    def _call(self, name: str, *args: Any) -> Any:
        fn = getattr(self._api, name)
        for attempt in range(2):
            try:
                return fn(*args)
            except Exception:
                if attempt:
                    raise
                time.sleep(1.5)
        return None  # pragma: no cover - unreachable

    # -- per-day metrics ---------------------------------------------------- #
    def training_status(self, day: str) -> Any:
        return self._call("get_training_status", day)

    def hrv(self, day: str) -> Any:
        return self._call("get_hrv_data", day)

    def rhr(self, day: str) -> Any:
        return self._call("get_rhr_day", day)

    def sleep(self, day: str) -> Any:
        return self._call("get_sleep_data", day)

    # -- activities ------------------------------------------------------------ #
    def activities_by_date(self, start: str, end: str) -> list[dict[str, Any]]:
        return self._call("get_activities_by_date", start, end) or []

    # -- one-off profile numbers -------------------------------------------- #
    def full_name(self) -> str:
        try:
            return self._call("get_full_name") or ""
        except Exception:
            return ""

    def user_profile(self) -> Any:
        return self._call("get_user_profile")

    def personal_records(self) -> Any:
        return self._call("get_personal_record")

    def race_predictions(self) -> Any:
        return self._call("get_race_predictions")

    def endurance_score(self, day: str) -> Any:
        return self._call("get_endurance_score", day)

    def cycling_ftp(self) -> Any:
        return self._call("get_cycling_ftp")

    def training_readiness(self, day: str) -> Any:
        return self._call("get_training_readiness", day)
