"""Config loading: defaults, TOML parsing, local override, env override."""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from garmin_dashboard.config import load_settings

BASE = """
[windows]
load_weeks = 10
mileage_weeks = 8

[[races]]
name = "Test 10K"
date = 2026-09-06
"""


def test_missing_file_gives_defaults(tmp_path: Path) -> None:
    s = load_settings(tmp_path / "absent.toml")
    assert s.windows.load_weeks == 12
    assert s.windows.recovery_weeks == 6
    assert s.races == ()


def test_parses_windows_and_races(tmp_path: Path) -> None:
    p = tmp_path / "config.toml"
    p.write_text(BASE)
    s = load_settings(p)
    assert s.windows.load_weeks == 10
    assert s.windows.mileage_weeks == 8
    assert s.windows.table_days == 28  # untouched default
    assert len(s.races) == 1
    assert s.races[0].name == "Test 10K"
    assert s.races[0].date == dt.date(2026, 9, 6)


def test_local_override_merges(tmp_path: Path) -> None:
    (tmp_path / "config.toml").write_text(BASE)
    (tmp_path / "config.local.toml").write_text("[windows]\nload_weeks = 4\n")
    s = load_settings(tmp_path / "config.toml")
    assert s.windows.load_weeks == 4
    assert s.windows.mileage_weeks == 8  # from base, untouched


def test_env_overrides_token_store(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "config.toml").write_text(BASE)
    monkeypatch.setenv("GARMINTOKENS", "/custom/tokens")
    s = load_settings(tmp_path / "config.toml")
    assert s.token_store == "/custom/tokens"


def test_default_token_store_is_expanded(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("GARMINTOKENS", raising=False)
    s = load_settings(tmp_path / "config.toml")
    assert s.token_store.endswith("/.garminconnect")
    assert "~" not in s.token_store
