# /// script
# requires-python = ">=3.11"
# dependencies = ["garminconnect==0.3.2", "jinja2>=3.1"]
# ///
"""Thin launcher for the ``garmin_dashboard`` package.

    uv run dashboard.py                 # fetch + render ./index.html
    uv run dashboard.py --demo          # synthetic data, no Garmin login
    uv run python -m garmin_dashboard   # equivalent

Kept so there's a single obvious entry point without installing anything. All
the real code lives in ``garmin_dashboard/``.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from garmin_dashboard.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
