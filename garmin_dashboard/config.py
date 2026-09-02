"""Load dashboard settings from ``config.toml`` (+ ``config.local.toml``) and env."""

from __future__ import annotations

import datetime as dt
import os
import tomllib
from pathlib import Path
from typing import Any

from .models import Race, Settings, Windows

DEFAULT_TOKEN_STORE = "~/.garminconnect"


def _deep_merge(base: dict[str, Any], over: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _as_date(value: Any) -> dt.date:
    if isinstance(value, dt.date):
        return value
    if isinstance(value, str):
        return dt.date.fromisoformat(value)
    raise TypeError(f"race date must be a date or YYYY-MM-DD string, got {value!r}")


def load_settings(config_path: str | os.PathLike[str] | None = None) -> Settings:
    """Read config, applying ``config.local.toml`` and ``GARMINTOKENS`` on top."""
    path = Path(config_path) if config_path else Path("config.toml")
    raw: dict[str, Any] = {}
    if path.is_file():
        raw = tomllib.loads(path.read_text())

    local = path.with_name("config.local.toml")
    if local.is_file():
        raw = _deep_merge(raw, tomllib.loads(local.read_text()))

    win_raw = raw.get("windows", {})
    d = Windows()
    windows = Windows(
        load_weeks=int(win_raw.get("load_weeks", d.load_weeks)),
        recovery_weeks=int(win_raw.get("recovery_weeks", d.recovery_weeks)),
        mileage_weeks=int(win_raw.get("mileage_weeks", d.mileage_weeks)),
        table_days=int(win_raw.get("table_days", d.table_days)),
        refetch_recent_days=int(win_raw.get("refetch_recent_days", d.refetch_recent_days)),
    )

    races = tuple(
        Race(name=str(r["name"]), date=_as_date(r["date"]))
        for r in raw.get("races", [])
        if r.get("name") and r.get("date")
    )

    token_store = os.path.expanduser(
        os.getenv("GARMINTOKENS") or str(raw.get("token_store") or DEFAULT_TOKEN_STORE)
    )

    return Settings(windows=windows, races=races, token_store=token_store)
