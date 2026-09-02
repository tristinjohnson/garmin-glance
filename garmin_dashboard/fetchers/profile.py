"""One-off profile / performance numbers: PRs, predictions, endurance, FTP, ..."""

from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Callable
from typing import Any, TypeVar

from ..garmin_client import GarminClient
from ..models import PersonalRecord, Profile
from ..transform import fmt_dur

log = logging.getLogger(__name__)

# Only the clean, unambiguous distance PRs. Garmin's 40K/100K "cycling" PRs on
# this account store inconsistent units, so they are intentionally excluded.
PR_LABELS: dict[int, str] = {
    1: "1 km",
    2: "1 mile",
    3: "5K",
    4: "10K",
    5: "Half Marathon",
    6: "Marathon",
    18: "100 m swim",
    19: "400 m swim",
    22: "1500 m swim",
    23: "1 mi swim",
}
PR_RUN = {1, 2, 3, 4, 5, 6}
ENDURANCE_TIERS: list[tuple[str, str]] = [
    ("classificationLowerLimitElite", "Elite"),
    ("classificationLowerLimitSuperior", "Superior"),
    ("classificationLowerLimitExpert", "Expert"),
    ("classificationLowerLimitWellTrained", "Well trained"),
    ("classificationLowerLimitTrained", "Trained"),
    ("classificationLowerLimitIntermediate", "Intermediate"),
]

T = TypeVar("T")


def _safe(label: str, fn: Callable[[], T]) -> T | None:
    try:
        return fn()
    except Exception as exc:
        log.warning("%s: %s", label, exc)
        return None


def _parse_user_profile(raw: Any) -> dict[str, Any]:
    ud = (raw or {}).get("userData") or {}
    weight = ud.get("weight")
    return {
        "height_cm": ud.get("height"),
        "weight_kg": round(weight / 1000, 1) if weight else None,
        "vo2_run": ud.get("vo2MaxRunning"),
        "vo2_bike": ud.get("vo2MaxCycling"),
        "lthr": ud.get("lactateThresholdHeartRate"),
    }


def _parse_prs(raw: Any) -> tuple[PersonalRecord, ...]:
    out: list[PersonalRecord] = []
    for r in raw or []:
        tid = r.get("typeId")
        if tid not in PR_LABELS:
            continue
        out.append(
            PersonalRecord(
                label=PR_LABELS[tid],
                value=fmt_dur(r.get("value")),
                grp="run" if tid in PR_RUN else "tri",
            )
        )
    return tuple(out)


def _parse_predictions(raw: Any) -> dict[str, str]:
    rp = raw or {}
    return {
        "5K": fmt_dur(rp.get("time5K")),
        "10K": fmt_dur(rp.get("time10K")),
        "Half": fmt_dur(rp.get("timeHalfMarathon")),
        "Marathon": fmt_dur(rp.get("timeMarathon")),
    }


def _endurance_class(es: dict[str, Any], score: float | None) -> str:
    if score is None:
        return "Beginner"
    for key, name in ENDURANCE_TIERS:
        limit = es.get(key)
        if limit is not None and score >= limit:
            return name
    return "Beginner"


def fetch_profile(client: GarminClient, today: dt.date) -> Profile:
    data: dict[str, Any] = {}

    up = _safe("profile", client.user_profile)
    if up is not None:
        data.update(_parse_user_profile(up))

    recs = _safe("personal records", client.personal_records)
    if recs is not None:
        data["prs"] = _parse_prs(recs)

    preds = _safe("race predictions", client.race_predictions)
    if preds is not None:
        data["predictions"] = _parse_predictions(preds)

    es = _safe("endurance score", lambda: client.endurance_score(today.isoformat()))
    if isinstance(es, dict):
        score = es.get("overallScore") or es.get("enduranceScore")
        data["endurance"] = score
        data["endurance_class"] = _endurance_class(es, score)

    ftp = _safe("ftp", client.cycling_ftp)
    if isinstance(ftp, dict):
        data["ftp"] = ftp.get("functionalThresholdPower") or ftp.get("cyclingFtp") or ftp.get("ftp")

    tr = _safe("training readiness", lambda: client.training_readiness(today.isoformat()))
    if isinstance(tr, list) and tr:
        data["readiness"] = tr[0].get("score")
        data["readiness_level"] = tr[0].get("level")

    return Profile(**data)
