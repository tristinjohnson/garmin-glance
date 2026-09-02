"""Per-day JSON cache so repeat runs only re-fetch the most recent days."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DayRecord = dict[str, Any]


class DayCache:
    """``{"daily": {"2026-06-10": {..., "_have": ["load", "hrv"]}}}`` on disk."""

    def __init__(self, path: Path, daily: dict[str, DayRecord] | None = None) -> None:
        self.path = path
        self.daily: dict[str, DayRecord] = daily or {}

    @classmethod
    def load(cls, path: str | Path) -> DayCache:
        p = Path(path)
        if p.is_file():
            try:
                raw = json.loads(p.read_text())
                if isinstance(raw, dict) and isinstance(raw.get("daily"), dict):
                    return cls(p, raw["daily"])
            except (OSError, ValueError):
                pass
        return cls(p, {})

    def save(self) -> None:
        self.path.write_text(json.dumps({"daily": self.daily}, separators=(",", ":")))

    # -- record access ---------------------------------------------------- #
    def record(self, day: str) -> DayRecord:
        return self.daily.setdefault(day, {})

    def have(self, day: str) -> set[str]:
        return set(self.daily.get(day, {}).get("_have", []))

    def mark(self, day: str, stream: str) -> None:
        rec = self.record(day)
        rec["_have"] = sorted(set(rec.get("_have", [])) | {stream})

    def get(self, day: str, field: str) -> Any:
        return self.daily.get(day, {}).get(field)

    def latest(self, field: str) -> tuple[str | None, Any]:
        for day in sorted(self.daily, reverse=True):
            val = self.daily[day].get(field)
            if val is not None:
                return day, val
        return None, None
