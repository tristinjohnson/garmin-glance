# /// script
# requires-python = ">=3.10"
# dependencies = ["garminconnect==0.3.2"]
# ///
"""
dashboard.py -- self-contained triathlon training dashboard from Garmin Connect.

WHAT IT DOES
    Reuses the OAuth tokens already cached at ~/.garminconnect (via the
    garminconnect library) -- it never asks for a password -- pulls your
    training data, and writes a single self-contained index.html next to this
    script. Open that file in a browser. Re-run any time to refresh.

USAGE
    uv run dashboard.py         # recommended: uv installs the one dependency
    python dashboard.py         # works too if `garminconnect==0.3.2` is installed

    A small .dashboard_cache.json is written beside this script so repeat runs
    only re-fetch the most recent days and finish in a few seconds. Delete it to
    force a full rebuild.

EDIT ME
    RACES below -- name + date (YYYY-MM-DD) for each event you're targeting.

CREDITS
    Built on python-garminconnect (cyberjunky) and bootstrapped with the
    garmin_mcp auth CLI (Taxuspt). Not affiliated with Garmin.
      https://github.com/cyberjunky/python-garminconnect
      https://github.com/Taxuspt/garmin_mcp

NOTE
    This is the frozen single-file prototype. The maintained version is the
    garmin_dashboard package in the parent directory.
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import sys
from pathlib import Path

# --------------------------------------------------------------------------- #
# CONFIG                                                                       #
# --------------------------------------------------------------------------- #
RACES = [
    {"name": "Around the Crown 10K", "date": "2026-09-06"},
    {"name": "IRONMAN 70.3 Augusta", "date": "2026-09-27"},
    {"name": "Space Coast Marathon", "date": "2026-11-22"},
]

TOKENSTORE = os.path.expanduser(os.getenv("GARMINTOKENS", "~/.garminconnect"))
HERE = Path(__file__).resolve().parent
OUT_HTML = HERE / "index.html"
CACHE_FILE = HERE / ".dashboard_cache.json"

LOAD_WEEKS = 12           # CTL / ATL / TSB + VO2 max trend window
RECOVERY_WEEKS = 6        # HRV / resting HR / sleep window
MILEAGE_WEEKS = 12        # weekly run/bike/swim volume window
TABLE_DAYS = 28           # recent-activities table window
REFETCH_RECENT_DAYS = 3   # always re-pull the last N days (data still settling)

M_TO_MI = 1.0 / 1609.344
M_TO_KM = 1.0 / 1000.0
MPS_TO_MPH = 2.2369362920544
KG_TO_LB = 2.2046226218

RUN_TYPES = {
    "running", "trail_running", "treadmill_running", "track_running",
    "virtual_run", "indoor_running", "obstacle_run", "ultra_run",
}
BIKE_TYPES = {
    "cycling", "road_biking", "mountain_biking", "gravel_cycling", "virtual_ride",
    "indoor_cycling", "cyclocross", "track_cycling", "bmx", "e_bike_fitness",
    "e_bike_mountain", "downhill_biking", "recumbent_cycling",
}
SWIM_TYPES = {"lap_swimming", "open_water_swimming", "swimming"}


# --------------------------------------------------------------------------- #
# small helpers                                                                #
# --------------------------------------------------------------------------- #
def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def daterange(start: dt.date, end: dt.date):
    d = start
    while d <= end:
        yield d
        d += dt.timedelta(days=1)


def week_start(d: dt.date) -> dt.date:
    """Monday that begins the week containing d (ISO week)."""
    return d - dt.timedelta(days=d.weekday())


def hhmm(seconds: float | None) -> str:
    if not seconds:
        return "--"
    s = int(round(seconds))
    h, rem = divmod(s, 3600)
    m, _ = divmod(rem, 60)
    return f"{h}:{m:02d}" if h else f"{m}:{_ + 0:02d}"


def mmss(seconds: float | None) -> str:
    if not seconds or seconds <= 0 or math.isinf(seconds):
        return "--"
    s = int(round(seconds))
    m, sec = divmod(s, 60)
    return f"{m}:{sec:02d}"


def fmt_dur(seconds: float | None) -> str:
    """H:MM:SS (or M:SS under an hour), truncated -- matches Garmin PR display."""
    if not seconds or seconds <= 0:
        return "--"
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


# --------------------------------------------------------------------------- #
# Garmin connection                                                            #
# --------------------------------------------------------------------------- #
def connect():
    try:
        from garminconnect import Garmin
    except ImportError:
        sys.exit(
            "The `garminconnect` package is not available.\n"
            "  Run with uv:   uv run dashboard.py\n"
            "  Or install:    pip install 'garminconnect==0.3.2'"
        )
    g = Garmin()
    try:
        g.login(TOKENSTORE)                      # resumes cached OAuth tokens
    except Exception as e:
        sys.exit(
            f"Garmin login with cached tokens failed ({TOKENSTORE}): {e}\n"
            "Re-run the Garmin MCP auth step to refresh the token, then retry."
        )
    return g


# --------------------------------------------------------------------------- #
# cache                                                                        #
# --------------------------------------------------------------------------- #
def load_cache() -> dict:
    if CACHE_FILE.exists():
        try:
            c = json.loads(CACHE_FILE.read_text())
            if isinstance(c, dict) and isinstance(c.get("daily"), dict):
                return c
        except Exception:
            pass
    return {"daily": {}}


def save_cache(c: dict) -> None:
    CACHE_FILE.write_text(json.dumps(c, separators=(",", ":")))


# --------------------------------------------------------------------------- #
# per-day fetch (training load, VO2, HRV, resting HR, sleep)                    #
# --------------------------------------------------------------------------- #
DAY_STREAMS = ("load", "hrv", "rhr", "sleep")


def _pull_load(g, k, rec):
    ts = g.get_training_status(k) or {}
    recent = (ts.get("mostRecentTrainingStatus") or {})
    latest = (recent.get("latestTrainingStatusData") or {})
    sd = {}
    for dev in latest.values():
        if isinstance(dev, dict):
            sd = dev
            if dev.get("primaryTrainingDevice"):
                break
    atl = sd.get("acuteTrainingLoadDTO") or {}
    a = atl.get("dailyTrainingLoadAcute")
    c = atl.get("dailyTrainingLoadChronic")
    rec["atl"] = round(a, 1) if isinstance(a, (int, float)) else None
    rec["ctl"] = round(c, 1) if isinstance(c, (int, float)) else None
    rec["tsb"] = round(c - a, 1) if isinstance(a, (int, float)) and isinstance(c, (int, float)) else None
    acwr = atl.get("dailyAcuteChronicWorkloadRatio")
    rec["acwr"] = round(acwr, 2) if isinstance(acwr, (int, float)) else None
    rec["acwr_status"] = atl.get("acwrStatus")
    rec["ts_phrase"] = sd.get("trainingStatusFeedbackPhrase")
    v = ts.get("mostRecentVO2Max") or {}
    gen = (v.get("generic") or {}) if isinstance(v.get("generic"), dict) else {}
    cyc = (v.get("cycling") or {}) if isinstance(v.get("cycling"), dict) else {}
    rec["vo2"] = gen.get("vo2MaxPreciseValue") or gen.get("vo2MaxValue")
    rec["vo2_cycling"] = cyc.get("vo2MaxPreciseValue") or cyc.get("vo2MaxValue")


def _pull_hrv(g, k, rec):
    hv = g.get_hrv_data(k) or {}
    s = hv.get("hrvSummary") or {}
    rec["hrv_weekly"] = s.get("weeklyAvg")
    rec["hrv_last"] = s.get("lastNightAvg")
    rec["hrv_status"] = s.get("status")
    base = s.get("baseline") or {}
    rec["hrv_base_low"] = base.get("balancedLow")
    rec["hrv_base_high"] = base.get("balancedUpper")


def _pull_rhr(g, k, rec):
    rd = g.get_rhr_day(k) or {}
    mm = (((rd.get("allMetrics") or {}).get("metricsMap") or {})
          .get("WELLNESS_RESTING_HEART_RATE") or [])
    rec["rhr"] = (mm[0].get("value") if mm and isinstance(mm[0], dict) else None)


def _pull_sleep(g, k, rec):
    sl = g.get_sleep_data(k) or {}
    dto = sl.get("dailySleepDTO") or {}
    sec = dto.get("sleepTimeSeconds") or 0
    rec["sleep_h"] = round(sec / 3600, 2) if sec else None
    rec["deep_h"] = round((dto.get("deepSleepSeconds") or 0) / 3600, 2)
    rec["light_h"] = round((dto.get("lightSleepSeconds") or 0) / 3600, 2)
    rec["rem_h"] = round((dto.get("remSleepSeconds") or 0) / 3600, 2)
    rec["awake_h"] = round((dto.get("awakeSleepSeconds") or 0) / 3600, 2)
    scores = dto.get("sleepScores") or {}
    overall = scores.get("overall") or {}
    rec["sleep_score"] = overall.get("value")


_PULLERS = {"load": _pull_load, "hrv": _pull_hrv, "rhr": _pull_rhr, "sleep": _pull_sleep}


def fetch_daily(g, cache, start: dt.date, end: dt.date, streams) -> None:
    today = dt.date.today()
    daily = cache["daily"]
    todo: list[tuple[str, list[str]]] = []
    for d in daterange(start, end):
        k = d.isoformat()
        rec = daily.get(k, {})
        have = set(rec.get("_have", []))
        need = [s for s in streams if s not in have]
        if (today - d).days <= REFETCH_RECENT_DAYS:
            need = list(streams)
        if need:
            todo.append((k, need))

    if not todo:
        return
    log(f"Fetching {len(todo)} day(s) x {len(streams)} stream(s) from Garmin ...")
    for i, (k, need) in enumerate(todo, 1):
        rec = daily.setdefault(k, {})
        have = set(rec.get("_have", []))
        for s in need:
            try:
                _PULLERS[s](g, k, rec)
                have.add(s)
            except Exception as e:
                log(f"  {k}/{s}: {e}")
        rec["_have"] = sorted(have)
        if i % 20 == 0:
            log(f"  ... {i}/{len(todo)}")
            save_cache(cache)
    save_cache(cache)


# --------------------------------------------------------------------------- #
# activities                                                                   #
# --------------------------------------------------------------------------- #
def sport_of(type_key: str) -> str | None:
    if type_key in RUN_TYPES:
        return "run"
    if type_key in BIKE_TYPES:
        return "bike"
    if type_key in SWIM_TYPES:
        return "swim"
    return None


def fetch_activities(g, start: dt.date, end: dt.date) -> list[dict]:
    raw = g.get_activities_by_date(start.isoformat(), end.isoformat()) or []
    out = []
    for a in raw:
        tk = ((a.get("activityType") or {}).get("typeKey")) or ""
        if tk == "multi_sport":
            continue                              # children are listed separately
        sp = sport_of(tk)
        if sp is None:
            continue
        st = a.get("startTimeLocal") or a.get("startTimeGMT") or ""
        dist = float(a.get("distance") or 0.0)
        dur = float(a.get("duration") or a.get("elapsedDuration") or 0.0)
        moving = float(a.get("movingDuration") or dur or 0.0)
        spd = a.get("averageSpeed")
        if not spd and dist and moving:
            spd = dist / moving
        out.append({
            "id": a.get("activityId"),
            "date": st[:10],
            "start": st,
            "name": a.get("activityName") or tk.replace("_", " ").title(),
            "sport": sp,
            "type_key": tk,
            "dist_m": dist,
            "dur_s": dur,
            "moving_s": moving,
            "avg_hr": a.get("averageHR"),
            "max_hr": a.get("maxHR"),
            "speed_mps": spd or 0.0,
            "elev_gain_m": a.get("elevationGain"),
        })
    out.sort(key=lambda x: x["start"])
    return out


def weekly_totals(acts: list[dict]) -> dict:
    """Per-week distance and time by sport, weeks running Monday -> Sunday."""
    today = dt.date.today()
    weeks = []
    cur = week_start(today) - dt.timedelta(weeks=MILEAGE_WEEKS - 1)
    while cur <= week_start(today):
        weeks.append(cur)
        cur += dt.timedelta(weeks=1)
    idx = {w.isoformat(): i for i, w in enumerate(weeks)}
    n = len(weeks)

    dist = {"run": [0.0] * n, "bike": [0.0] * n, "swim": [0.0] * n}
    time = {"run": [0.0] * n, "bike": [0.0] * n, "swim": [0.0] * n}
    for a in acts:
        try:
            ws = week_start(dt.date.fromisoformat(a["date"])).isoformat()
        except Exception:
            continue
        i = idx.get(ws)
        if i is None:
            continue
        sp = a["sport"]
        dist[sp][i] += a["dist_m"] * (M_TO_KM if sp == "swim" else M_TO_MI)
        time[sp][i] += (a["dur_s"] or 0) / 3600.0

    def pack(series, units):
        return {sp: {"unit": units[sp], "values": [round(x, 1) for x in series[sp]]}
                for sp in ("run", "bike", "swim")}

    return {
        "labels": [w.strftime("%b %-d") for w in weeks],
        "dist": pack(dist, {"run": "mi", "bike": "mi", "swim": "km"}),
        "time": pack(time, {"run": "h", "bike": "h", "swim": "h"}),
    }


def recent_table(acts: list[dict]) -> list[dict]:
    cutoff = (dt.date.today() - dt.timedelta(days=TABLE_DAYS)).isoformat()
    rows = []
    for a in acts:
        if a["date"] < cutoff:
            continue
        spd = a["speed_mps"]
        if a["sport"] == "run":
            dist_txt = f"{a['dist_m'] * M_TO_MI:.2f} mi"
            pace_txt = f"{mmss(1609.344 / spd)} /mi" if spd else "--"
        elif a["sport"] == "bike":
            dist_txt = f"{a['dist_m'] * M_TO_MI:.2f} mi"
            pace_txt = f"{spd * MPS_TO_MPH:.1f} mph" if spd else "--"
        else:
            dist_txt = f"{a['dist_m']:.0f} m"
            pace_txt = f"{mmss(100.0 / spd)} /100m" if spd else "--"
        rows.append({
            "date": a["date"],
            "sport": a["sport"],
            "name": a["name"],
            "type": a["type_key"].replace("_", " "),
            "dist": dist_txt,
            "pace": pace_txt,
            "dur": hhmm(a["dur_s"]),
            "hr": int(a["avg_hr"]) if a["avg_hr"] else None,
        })
    rows.sort(key=lambda r: r["date"], reverse=True)
    return rows


# --------------------------------------------------------------------------- #
# derived series from the daily cache                                          #
# --------------------------------------------------------------------------- #
def series(cache, start: dt.date, end: dt.date, field: str):
    daily = cache["daily"]
    labels, vals = [], []
    for d in daterange(start, end):
        labels.append(d.isoformat())
        vals.append(daily.get(d.isoformat(), {}).get(field))
    return labels, vals


def carry_forward(vals):
    out, last = [], None
    for v in vals:
        if v is not None:
            last = v
        out.append(last)
    return out


def latest_value(cache, field):
    for k in sorted(cache["daily"], reverse=True):
        v = cache["daily"][k].get(field)
        if v is not None:
            return k, v
    return None, None


# --------------------------------------------------------------------------- #
# one-off profile / performance numbers                                        #
# --------------------------------------------------------------------------- #
# Only the clean, unambiguous distance PRs. Garmin's 40K/100K "cycling" PRs on
# this account store inconsistent units, so they are intentionally excluded.
PR_LABELS = {
    1: "1 km", 2: "1 mile", 3: "5K", 4: "10K", 5: "Half Marathon", 6: "Marathon",
    18: "100 m swim", 19: "400 m swim", 22: "1500 m swim", 23: "1 mi swim",
}
PR_RUN = {1, 2, 3, 4, 5, 6}
PR_TRI = {18, 19, 22, 23}
ENDURANCE_TIERS = [
    ("classificationLowerLimitElite", "Elite"),
    ("classificationLowerLimitSuperior", "Superior"),
    ("classificationLowerLimitExpert", "Expert"),
    ("classificationLowerLimitWellTrained", "Well trained"),
    ("classificationLowerLimitTrained", "Trained"),
    ("classificationLowerLimitIntermediate", "Intermediate"),
]


def get_profile_bits(g) -> dict:
    out: dict = {}
    try:
        prof = g.get_user_profile() or {}
        ud = prof.get("userData") or {}
        out["height_cm"] = ud.get("height")
        out["weight_kg"] = round(ud.get("weight") / 1000, 1) if ud.get("weight") else None
        out["vo2_run"] = ud.get("vo2MaxRunning")
        out["vo2_bike"] = ud.get("vo2MaxCycling")
        out["lthr"] = ud.get("lactateThresholdHeartRate")
    except Exception as e:
        log(f"profile: {e}")

    try:
        recs = g.get_personal_record() or []
        prs = []
        for r in recs:
            tid = r.get("typeId")
            if tid not in PR_LABELS:
                continue
            prs.append({
                "label": PR_LABELS[tid],
                "value": fmt_dur(r.get("value")),
                "grp": "run" if tid in PR_RUN else "tri",
            })
        out["prs"] = prs
    except Exception as e:
        log(f"personal records: {e}")

    try:
        rp = g.get_race_predictions() or {}
        out["predictions"] = {
            "5K": fmt_dur(rp.get("time5K")),
            "10K": fmt_dur(rp.get("time10K")),
            "Half": fmt_dur(rp.get("timeHalfMarathon")),
            "Marathon": fmt_dur(rp.get("timeMarathon")),
        }
    except Exception as e:
        log(f"race predictions: {e}")

    try:
        es = g.get_endurance_score(dt.date.today().isoformat())
        if isinstance(es, dict):
            score = es.get("overallScore") or es.get("enduranceScore")
            out["endurance"] = score
            label = None
            for key, name in ENDURANCE_TIERS:
                lim = es.get(key)
                if score is not None and lim is not None and score >= lim:
                    label = name
                    break
            out["endurance_class"] = label or "Beginner"
    except Exception as e:
        log(f"endurance score: {e}")

    try:
        ftp = g.get_cycling_ftp() or {}
        if isinstance(ftp, dict):
            out["ftp"] = (ftp.get("functionalThresholdPower")
                          or ftp.get("cyclingFtp") or ftp.get("ftp"))
    except Exception as e:
        log(f"ftp: {e}")

    try:
        tr = g.get_training_readiness(dt.date.today().isoformat())
        if isinstance(tr, list) and tr:
            out["readiness"] = tr[0].get("score")
            out["readiness_level"] = tr[0].get("level")
    except Exception as e:
        log(f"training readiness: {e}")

    return out


# --------------------------------------------------------------------------- #
# assemble everything                                                          #
# --------------------------------------------------------------------------- #
def build_data(g, cache) -> dict:
    today = dt.date.today()
    load_start = today - dt.timedelta(weeks=LOAD_WEEKS)
    rec_start = today - dt.timedelta(weeks=RECOVERY_WEEKS)
    act_start = min(load_start, week_start(today) - dt.timedelta(weeks=MILEAGE_WEEKS - 1))

    fetch_daily(g, cache, load_start, today, ("load",))
    fetch_daily(g, cache, rec_start, today, ("hrv", "rhr", "sleep"))

    log("Fetching activities ...")
    acts = fetch_activities(g, act_start, today)
    log(f"  {len(acts)} run/bike/swim activities in window")

    log("Fetching profile & performance numbers ...")
    prof = get_profile_bits(g)
    try:
        athlete = g.get_full_name() or ""
    except Exception:
        athlete = ""

    # ---- training load / form ------------------------------------------------
    l_labels, ctl = series(cache, load_start, today, "ctl")
    _, atl = series(cache, load_start, today, "atl")
    _, tsb = series(cache, load_start, today, "tsb")
    _, vo2_raw = series(cache, load_start, today, "vo2")
    vo2 = carry_forward(vo2_raw)

    # ---- recovery ----------------------------------------------------------
    r_labels, hrv_weekly = series(cache, rec_start, today, "hrv_weekly")
    _, hrv_last = series(cache, rec_start, today, "hrv_last")
    _, rhr = series(cache, rec_start, today, "rhr")
    _, sleep_h = series(cache, rec_start, today, "sleep_h")
    _, sleep_score = series(cache, rec_start, today, "sleep_score")
    _, hrv_lo = series(cache, rec_start, today, "hrv_base_low")
    _, hrv_hi = series(cache, rec_start, today, "hrv_base_high")
    hrv_lo = carry_forward(hrv_lo)
    hrv_hi = carry_forward(hrv_hi)

    d_ctl = latest_value(cache, "ctl")
    d_atl = latest_value(cache, "atl")
    d_tsb = latest_value(cache, "tsb")
    d_phrase = latest_value(cache, "ts_phrase")
    d_acwr = latest_value(cache, "acwr")
    d_rhr = latest_value(cache, "rhr")
    d_hrv = latest_value(cache, "hrv_weekly")
    d_hrv_status = latest_value(cache, "hrv_status")
    d_vo2 = latest_value(cache, "vo2")
    d_vo2_bike = latest_value(cache, "vo2_cycling")

    races = []
    for r in RACES:
        rd = dt.date.fromisoformat(r["date"])
        days = (rd - today).days
        races.append({
            "name": r["name"],
            "date": r["date"],
            "date_fmt": rd.strftime("%a, %b %-d, %Y"),
            "days": days,
            "weeks": round(days / 7, 1),
            "past": days < 0,
        })
    upcoming = [r for r in races if not r["past"]]
    next_race = min(upcoming, key=lambda r: r["days"]) if upcoming else None

    return {
        "generated": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "today": today.isoformat(),
        "athlete": (f"/ {athlete}" if athlete else ""),
        "windows": {"load": LOAD_WEEKS, "recovery": RECOVERY_WEEKS, "mileage": MILEAGE_WEEKS, "table": TABLE_DAYS},
        "races": races,
        "next_race": next_race,
        "profile": prof,
        "snapshot": {
            "ctl": d_ctl[1], "atl": d_atl[1], "tsb": d_tsb[1], "acwr": d_acwr[1],
            "ts_phrase": d_phrase[1], "ts_date": d_phrase[0],
            "vo2_run": d_vo2[1], "vo2_bike": d_vo2_bike[1],
            "rhr": d_rhr[1], "hrv": d_hrv[1], "hrv_status": d_hrv_status[1],
        },
        "load": {
            "labels": l_labels, "ctl": ctl, "atl": atl, "tsb": tsb,
        },
        "vo2": {"labels": l_labels, "values": vo2},
        "weekly": weekly_totals(acts),
        "recovery": {
            "labels": r_labels,
            "hrv_weekly": hrv_weekly, "hrv_last": hrv_last,
            "hrv_lo": hrv_lo, "hrv_hi": hrv_hi,
            "rhr": rhr, "sleep_h": sleep_h, "sleep_score": sleep_score,
        },
        "table": recent_table(acts),
    }


# --------------------------------------------------------------------------- #
# HTML                                                                         #
# --------------------------------------------------------------------------- #
HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Training Dashboard</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
  :root{
    color-scheme:light;
    --bg:#f4f5f7; --card:#ffffff; --ink:#1c2530; --muted:#67727e; --line:#e4e7eb;
    --soft:#fafbfc; --pill:#eef1f4; --grid:#e9ecef;
    --run:#e8663c; --bike:#2f7fd1; --swim:#1aa89a; --ctl:#2f7fd1; --atl:#e8663c;
    --tsb:#5c9e57; --accent:#1c2530; --accent-ink:#ffffff;
  }
  /* dark palette: default when the OS asks for dark and the user hasn't forced light */
  @media (prefers-color-scheme:dark){
    :root:not([data-theme="light"]){
      color-scheme:dark;
      --bg:#131619; --card:#1d2126; --ink:#e8ecef; --muted:#9aa5af; --line:#2c333b;
      --soft:#23282e; --pill:#2a3037; --grid:#2b323a;
      --accent:#e8ecef; --accent-ink:#131619;
    }
  }
  /* explicit override from the toggle button */
  :root[data-theme="dark"]{
    color-scheme:dark;
    --bg:#131619; --card:#1d2126; --ink:#e8ecef; --muted:#9aa5af; --line:#2c333b;
    --soft:#23282e; --pill:#2a3037; --grid:#2b323a;
    --accent:#e8ecef; --accent-ink:#131619;
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);
    font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;}
  a{color:inherit}
  .wrap{max-width:1180px;margin:0 auto;padding:28px 20px 60px}
  header.top{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:10px;margin-bottom:18px}
  header.top h1{font-size:20px;margin:0;font-weight:650}
  .meta-right{display:flex;align-items:center;gap:10px;flex-wrap:wrap;justify-content:flex-end}
  .stamp{color:var(--muted);font-size:12px}
  .theme-btn{font:inherit;font-size:12px;padding:5px 11px;border:1px solid var(--line);border-radius:999px;
    background:var(--card);color:var(--ink);cursor:pointer;line-height:1;white-space:nowrap}
  .theme-btn:hover{border-color:var(--muted)}
  .card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:20px;margin-bottom:20px;
    box-shadow:0 1px 2px rgba(16,24,40,.04)}
  .card h2{font-size:13px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);margin:0 0 14px}
  .card .sub{color:var(--muted);font-size:12px;margin:-8px 0 14px}

  /* countdown */
  .countdown{display:grid;grid-template-columns:1.1fr 1fr;gap:22px;align-items:center}
  .cd-main .lead{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.06em}
  .cd-main .race{font-size:22px;font-weight:650;margin:2px 0 6px}
  .cd-main .big{font-size:52px;font-weight:720;line-height:1;letter-spacing:-.02em}
  .cd-main .big span{font-size:20px;font-weight:550;color:var(--muted)}
  .cd-main .when{color:var(--muted);margin-top:6px}
  .cd-list{list-style:none;margin:0;padding:0}
  .cd-list li{display:flex;justify-content:space-between;gap:10px;padding:9px 0;border-bottom:1px dashed var(--line)}
  .cd-list li:last-child{border-bottom:0}
  .cd-list .nm{font-weight:550}
  .cd-list .meta{color:var(--muted);font-size:12px}
  .cd-list li.past{opacity:.45}
  .cd-list .rt{text-align:right;white-space:nowrap}
  .pill{display:inline-block;padding:1px 8px;border-radius:999px;font-size:11px;font-weight:600;
    background:var(--pill);color:var(--muted)}
  .pill.next{background:var(--accent);color:var(--accent-ink)}

  /* snapshot */
  .stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:14px}
  .stat{background:var(--soft);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
  .stat .k{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.05em}
  .stat .v{font-size:22px;font-weight:680;margin-top:3px}
  .stat .n{color:var(--muted);font-size:11px;margin-top:2px}

  .grid2{display:grid;grid-template-columns:1fr 1fr;gap:20px}
  .grid3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:20px}
  .chartbox{position:relative;height:300px}
  .chartbox.sm{height:220px}

  table{width:100%;border-collapse:collapse;font-size:13px}
  th,td{padding:8px 10px;text-align:left;border-bottom:1px solid var(--line);white-space:nowrap}
  th{font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);font-weight:600}
  td.name{white-space:normal;min-width:180px}
  .tag{font-size:11px;font-weight:650;padding:1px 7px;border-radius:6px;color:#fff}
  .tag.run{background:var(--run)} .tag.bike{background:var(--bike)} .tag.swim{background:var(--swim)}
  .tbl-scroll{overflow-x:auto}
  .prs{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
  .pr{border:1px solid var(--line);border-radius:9px;padding:9px 12px;background:var(--soft)}
  .pr .k{color:var(--muted);font-size:11px}.pr .v{font-weight:650;font-size:15px}
  .foot{color:var(--muted);font-size:12px;text-align:center;margin-top:26px}
  @media(max-width:860px){.countdown,.grid2,.grid3{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="wrap">
  <header class="top">
    <h1>Training Dashboard <span style="font-weight:400;color:var(--muted)">__ATHLETE__</span></h1>
    <div class="meta-right">
      <button id="themeBtn" class="theme-btn" type="button" aria-label="Toggle colour theme">Auto</button>
      <span class="stamp">refreshed __GENERATED__ &nbsp;·&nbsp; data through __TODAY__</span>
    </div>
  </header>

  <section class="card" id="countdown-card">
    <h2>Countdown</h2>
    <div class="countdown" id="countdown"></div>
  </section>

  <section class="card">
    <h2>Current fitness snapshot</h2>
    <div class="stats" id="snapshot"></div>
  </section>

  <section class="card">
    <h2>Training load &mdash; fitness / fatigue / form</h2>
    <div class="sub">CTL (fitness, 42-day load) · ATL (fatigue, 7-day load) · TSB = CTL &minus; ATL (form). Last __W_LOAD__ weeks.</div>
    <div class="chartbox"><canvas id="loadChart"></canvas></div>
  </section>

  <section class="card">
    <h2>Weekly volume &mdash; run / bike / swim</h2>
    <div class="sub">Distance per week, Monday&ndash;Sunday. Last __W_MILEAGE__ weeks. Multisport races counted via their individual legs.</div>
    <div class="grid3">
      <div><div class="chartbox sm"><canvas id="runMi"></canvas></div></div>
      <div><div class="chartbox sm"><canvas id="bikeMi"></canvas></div></div>
      <div><div class="chartbox sm"><canvas id="swimKm"></canvas></div></div>
    </div>
  </section>

  <section class="card">
    <h2>Weekly time &mdash; run / bike / swim</h2>
    <div class="sub">Hours per week, Monday&ndash;Sunday. Last __W_MILEAGE__ weeks.</div>
    <div class="grid3">
      <div><div class="chartbox sm"><canvas id="runHr"></canvas></div></div>
      <div><div class="chartbox sm"><canvas id="bikeHr"></canvas></div></div>
      <div><div class="chartbox sm"><canvas id="swimHr"></canvas></div></div>
    </div>
  </section>

  <section class="card">
    <h2>Recovery</h2>
    <div class="sub">Last __W_REC__ weeks. HRV shaded band = your balanced baseline range.</div>
    <div class="grid3">
      <div><div class="chartbox sm"><canvas id="hrvChart"></canvas></div></div>
      <div><div class="chartbox sm"><canvas id="rhrChart"></canvas></div></div>
      <div><div class="chartbox sm"><canvas id="sleepChart"></canvas></div></div>
    </div>
  </section>

  <section class="card">
    <h2>VO&#8322; max trend</h2>
    <div class="sub">Running VO&#8322; max estimate, last __W_LOAD__ weeks (days without a recompute carried forward).</div>
    <div class="chartbox"><canvas id="vo2Chart"></canvas></div>
  </section>

  <section class="card">
    <h2>Recent activities &mdash; last __TBL_DAYS__ days</h2>
    <div class="tbl-scroll"><table id="actTable">
      <thead><tr><th>Date</th><th>Sport</th><th>Workout</th><th>Distance</th><th>Pace / speed</th><th>Time</th><th>Avg HR</th></tr></thead>
      <tbody></tbody>
    </table></div>
  </section>

  <section class="card" id="pr-card">
    <h2>Personal records &amp; race predictions</h2>
    <div id="prBlock"></div>
  </section>

  <div class="foot">Generated by dashboard.py &mdash; re-run <code>uv run dashboard.py</code> to refresh.</div>
</div>

<script>
const DATA = __DATA__;
const C = {ink:'#1c2530',muted:'#67727e',grid:'#e9ecef',run:'#e8663c',bike:'#2f7fd1',swim:'#1aa89a',
           ctl:'#2f7fd1',atl:'#e8663c',tsb:'#5c9e57'};

if (typeof Chart === 'undefined') {
  document.querySelectorAll('.chartbox').forEach(b => {
    b.style.display = 'flex'; b.style.alignItems = 'center'; b.style.justifyContent = 'center';
    b.innerHTML = '<div style="color:var(--muted);font-size:13px;text-align:center">' +
      'Chart library did not load.<br>This page needs an internet connection ' +
      'the first time you open it (Chart.js loads from a CDN).</div>';
  });
  throw new Error('Chart.js failed to load from CDN');
}

Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
Chart.defaults.color = C.muted;
Chart.defaults.plugins.legend.labels.boxWidth = 12;
Chart.defaults.plugins.legend.labels.usePointStyle = true;
Chart.defaults.maintainAspectRatio = false;

const shortDate = s => { const d = new Date(s+'T00:00'); return d.toLocaleDateString('en-US',{month:'short',day:'numeric'}); };
const everyNth = (arr,n) => arr.map((v,i)=> i%n===0 ? v : '');

/* ---------- countdown ---------- */
(function(){
  const el = document.getElementById('countdown');
  const nr = DATA.next_race;
  const main = document.createElement('div'); main.className='cd-main';
  if(nr){
    main.innerHTML = `<div class="lead">Next race &mdash; ${nr.weeks} weeks out</div>
      <div class="race">${nr.name}</div>
      <div class="big">${nr.days}<span> days</span></div>
      <div class="when">${nr.date_fmt}</div>`;
  } else {
    main.innerHTML = `<div class="lead">No upcoming races configured</div>`;
  }
  const list = document.createElement('ul'); list.className='cd-list';
  DATA.races.forEach(r=>{
    const li = document.createElement('li');
    if(r.past) li.className='past';
    const isNext = nr && r.name===nr.name && r.date===nr.date;
    li.innerHTML = `<span><span class="nm">${r.name}</span><br><span class="meta">${r.date_fmt}</span></span>
      <span class="rt">${ r.past
        ? '<span class="pill">done</span>'
        : `<b>${r.days}d</b> &nbsp;<span class="meta">${r.weeks}w</span><br>`
          + (isNext?'<span class="pill next">next up</span>':'<span class="pill">upcoming</span>') }</span>`;
    list.appendChild(li);
  });
  el.appendChild(main); el.appendChild(list);
})();

/* ---------- snapshot ---------- */
(function(){
  const s = DATA.snapshot, p = DATA.profile || {};
  const tsbNote = s.tsb==null ? '' : (s.tsb<-20 ? 'deep in the work' : s.tsb>5 ? 'fresh' : 'building');
  const cells = [
    ['CTL — fitness', fmt(s.ctl,0), s.ts_phrase ? nicePhrase(s.ts_phrase) : ''],
    ['ATL — fatigue', fmt(s.atl,0), '7-day load'],
    ['TSB — form', (s.tsb>0?'+':'')+fmt(s.tsb,0), tsbNote],
    ['ACWR', fmt(s.acwr,2), 'acute : chronic'],
    ['VO₂ max — run', fmt(s.vo2_run ?? p.vo2_run,1), s.vo2_bike?('bike '+fmt(s.vo2_bike,1)):''],
    ['Resting HR', s.rhr==null?'—':fmt(s.rhr,0)+' bpm', ''],
    ['HRV — 7-day', s.hrv==null?'—':fmt(s.hrv,0)+' ms', s.hrv_status?titleCase(s.hrv_status):''],
    ['Endurance score', fmt(p.endurance,0), p.endurance_class || ''],
    ['Readiness', fmt(p.readiness,0), p.readiness_level?titleCase(p.readiness_level):''],
    ['Cycling FTP', p.ftp?fmt(p.ftp,0)+' W':'—', ''],
    ['Weight', p.weight_kg? (p.weight_kg*2.20462).toFixed(0)+' lb':'—', p.height_cm? htFt(p.height_cm):''],
  ];
  const wrap = document.getElementById('snapshot');
  cells.forEach(([k,v,n])=>{
    const d=document.createElement('div'); d.className='stat';
    d.innerHTML=`<div class="k">${k}</div><div class="v">${v}</div>${n?`<div class="n">${n}</div>`:''}`;
    wrap.appendChild(d);
  });
})();
function fmt(v,dec){ return (v===null||v===undefined||Number.isNaN(v))?'—':Number(v).toFixed(dec); }
function titleCase(s){ return String(s).toLowerCase().replace(/(^|[_\s])\w/g,m=>m.toUpperCase()).replace(/_/g,' '); }
function nicePhrase(s){ return titleCase(String(s).replace(/_\d+$/,'')); }
function htFt(cm){ const t=cm/2.54; return Math.floor(t/12)+"'"+Math.round(t%12)+'"'; }

/* ---------- charts (rebuilt whenever the theme changes) ---------- */
const CHARTS = [];
function themeVars(){
  const cs = getComputedStyle(document.documentElement);
  return {ink:cs.getPropertyValue('--ink').trim(),
          muted:cs.getPropertyValue('--muted').trim(),
          grid:cs.getPropertyValue('--grid').trim()};
}
function drawCharts(){
  CHARTS.forEach(c => c.destroy());
  CHARTS.length = 0;
  const T = themeVars();
  Chart.defaults.color = T.muted;

  /* training load */
  const L = DATA.load;
  CHARTS.push(new Chart(loadChart,{
    type:'line',
    data:{ labels:L.labels, datasets:[
      {type:'line',label:'CTL (fitness)',data:L.ctl,borderColor:C.ctl,backgroundColor:C.ctl,
        borderWidth:2,pointRadius:0,tension:.3,spanGaps:true,yAxisID:'y'},
      {type:'line',label:'ATL (fatigue)',data:L.atl,borderColor:C.atl,backgroundColor:C.atl,
        borderWidth:1.5,borderDash:[4,3],pointRadius:0,tension:.3,spanGaps:true,yAxisID:'y'},
      {type:'line',label:'TSB (form)',data:L.tsb,borderColor:C.tsb,backgroundColor:'rgba(92,158,87,.16)',
        borderWidth:1.5,pointRadius:0,tension:.3,spanGaps:true,fill:'origin',yAxisID:'y1'},
    ]},
    options:{interaction:{mode:'index',intersect:false},
      scales:{
        x:{grid:{display:false},ticks:{maxRotation:0,autoSkip:true,maxTicksLimit:9,callback:(v,i)=>shortDate(L.labels[i])}},
        y:{position:'left',title:{display:true,text:'CTL / ATL load'},grid:{color:T.grid}},
        y1:{position:'right',title:{display:true,text:'TSB'},grid:{drawOnChartArea:false}},
      }}
  }));

  /* weekly volume + weekly time (same style, Monday-Sunday buckets) */
  const W = DATA.weekly;
  const bars = (cvs,block,color,title)=> CHARTS.push(new Chart(cvs,{
    type:'bar',
    data:{ labels:W.labels, datasets:[
      {label:block.unit+'/wk',data:block.values,backgroundColor:color+'cc',borderRadius:3},
    ]},
    options:{plugins:{legend:{display:false},title:{display:true,text:title},
        tooltip:{callbacks:{label:c=>` ${c.parsed.y} ${block.unit}`}}},
      scales:{x:{grid:{display:false},ticks:{maxRotation:0,autoSkip:true,maxTicksLimit:7}},
              y:{beginAtZero:true,grid:{color:T.grid}}}}
  }));
  bars(runMi,  W.dist.run,  C.run,  'Run (mi/wk)');
  bars(bikeMi, W.dist.bike, C.bike, 'Bike (mi/wk)');
  bars(swimKm, W.dist.swim, C.swim, 'Swim (km/wk)');
  bars(runHr,  W.time.run,  C.run,  'Run (h/wk)');
  bars(bikeHr, W.time.bike, C.bike, 'Bike (h/wk)');
  bars(swimHr, W.time.swim, C.swim, 'Swim (h/wk)');

  /* recovery */
  const R = DATA.recovery, lab = R.labels;
  const tick = {maxRotation:0,autoSkip:true,maxTicksLimit:6,callback:(v,i)=>shortDate(lab[i])};
  CHARTS.push(new Chart(hrvChart,{
    type:'line',
    data:{labels:lab,datasets:[
      {label:'baseline high',data:R.hrv_hi,borderColor:'transparent',backgroundColor:'rgba(47,127,209,.13)',
        pointRadius:0,fill:'+1',spanGaps:true},
      {label:'baseline low',data:R.hrv_lo,borderColor:'transparent',backgroundColor:'rgba(47,127,209,.13)',
        pointRadius:0,fill:false,spanGaps:true},
      {label:'HRV 7-day avg',data:R.hrv_weekly,borderColor:C.bike,borderWidth:2,pointRadius:0,tension:.3,spanGaps:true},
      {label:'last night',data:R.hrv_last,borderColor:T.muted,borderWidth:1,pointRadius:1.5,showLine:false},
    ]},
    options:{plugins:{legend:{display:false},title:{display:true,text:'HRV (ms)'}},
      scales:{x:{grid:{display:false},ticks:tick},y:{grid:{color:T.grid}}}}
  }));
  CHARTS.push(new Chart(rhrChart,{
    type:'line',
    data:{labels:lab,datasets:[
      {label:'Resting HR',data:R.rhr,borderColor:C.atl,backgroundColor:'rgba(232,102,60,.16)',
        borderWidth:2,pointRadius:0,tension:.3,fill:true,spanGaps:true}]},
    options:{plugins:{legend:{display:false},title:{display:true,text:'Resting HR (bpm)'}},
      scales:{x:{grid:{display:false},ticks:tick},y:{grid:{color:T.grid}}}}
  }));
  CHARTS.push(new Chart(sleepChart,{
    type:'bar',
    data:{labels:lab,datasets:[
      {type:'bar',label:'Sleep (h)',data:R.sleep_h,order:2,borderRadius:3,
        backgroundColor:R.sleep_score.map(sc=> sc==null?T.grid: sc>=85?'#4f9d54': sc>=70?'#c9a227':'#c65b3c')},
    ]},
    options:{plugins:{legend:{display:false},title:{display:true,text:'Sleep (h) — green = good score'}},
      scales:{x:{grid:{display:false},ticks:tick},y:{beginAtZero:true,suggestedMax:10,grid:{color:T.grid}}}}
  }));

  /* VO2 max */
  const V = DATA.vo2, vv = V.values.filter(x=>x!=null);
  const lo = vv.length? Math.floor(Math.min(...vv)-1):0, hi = vv.length? Math.ceil(Math.max(...vv)+1):100;
  CHARTS.push(new Chart(vo2Chart,{
    type:'line',
    data:{labels:V.labels,datasets:[
      {label:'VO₂ max (run)',data:V.values,borderColor:C.tsb,backgroundColor:'rgba(92,158,87,.16)',
        borderWidth:2,pointRadius:0,tension:.3,fill:true,spanGaps:true}]},
    options:{plugins:{legend:{display:false}},
      scales:{x:{grid:{display:false},ticks:{maxRotation:0,autoSkip:true,maxTicksLimit:9,callback:(v,i)=>shortDate(V.labels[i])}},
              y:{min:lo,max:hi,grid:{color:T.grid}}}}
  }));
}

/* ---------- table ---------- */
(function(){
  const tb = document.querySelector('#actTable tbody');
  if(!DATA.table.length){ tb.innerHTML='<tr><td colspan="7" style="color:var(--muted)">No activities in window.</td></tr>'; return; }
  DATA.table.forEach(r=>{
    const tr=document.createElement('tr');
    tr.innerHTML = `<td>${shortDate(r.date)}</td>
      <td><span class="tag ${r.sport}">${r.sport}</span></td>
      <td class="name">${r.name}</td>
      <td>${r.dist}</td><td>${r.pace}</td><td>${r.dur}</td><td>${r.hr??'—'}</td>`;
    tb.appendChild(tr);
  });
})();

/* ---------- PRs + predictions ---------- */
(function(){
  const p = DATA.profile||{}, box = document.getElementById('prBlock');
  const groups = [['run','Running PRs'],['tri','Swim / bike PRs']];
  let html='';
  (p.prs||[]).length && groups.forEach(([g,title])=>{
    const items=(p.prs||[]).filter(x=>x.grp===g);
    if(!items.length) return;
    html += `<div style="margin-bottom:14px"><div class="k" style="color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.05em;margin-bottom:8px">${title}</div><div class="prs">`;
    items.forEach(it=> html += `<div class="pr"><div class="k">${it.label}</div><div class="v">${it.value}</div></div>`);
    html += `</div></div>`;
  });
  if(p.predictions){
    html += `<div><div class="k" style="color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.05em;margin-bottom:8px">Garmin race predictions (current fitness)</div><div class="prs">`;
    Object.entries(p.predictions).forEach(([k,v])=> v && v!=='--' && (html += `<div class="pr"><div class="k">${k}</div><div class="v">${v}</div></div>`));
    html += `</div></div>`;
  }
  box.innerHTML = html || '<span style="color:var(--muted)">No records returned.</span>';
})();

/* ---------- theme toggle (Auto -> Light -> Dark) ---------- */
(function(){
  const btn = document.getElementById('themeBtn');
  const MODES = [['auto','Auto'],['light','Light'],['dark','Dark']];
  function apply(mode){
    if(mode === 'auto') delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = mode;
    try{ localStorage.setItem('dash-theme', mode); }catch(e){}
    const m = MODES.find(x => x[0] === mode) || MODES[0];
    btn.textContent = m[1];
    btn.dataset.mode = m[0];
  }
  let mode = 'auto';
  try{ mode = localStorage.getItem('dash-theme') || 'auto'; }catch(e){}
  apply(mode);
  drawCharts();
  btn.addEventListener('click', () => {
    const i = MODES.findIndex(x => x[0] === (btn.dataset.mode || 'auto'));
    apply(MODES[(i + 1) % MODES.length][0]);
    drawCharts();
  });
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    if((btn.dataset.mode || 'auto') === 'auto') drawCharts();
  });
})();
</script>
</body>
</html>
"""


def render(data: dict) -> str:
    w = data["windows"]
    # escape "<" so an activity name containing "</script>" can't break the page
    payload = json.dumps(data).replace("<", "\\u003c")
    return (
        HTML.replace("__DATA__", payload)
        .replace("__ATHLETE__", data["athlete"])
        .replace("__GENERATED__", data["generated"])
        .replace("__TODAY__", data["today"])
        .replace("__W_LOAD__", str(w["load"]))
        .replace("__W_MILEAGE__", str(w["mileage"]))
        .replace("__W_REC__", str(w["recovery"]))
        .replace("__TBL_DAYS__", str(w["table"]))
    )


# --------------------------------------------------------------------------- #
def main() -> None:
    g = connect()
    cache = load_cache()
    data = build_data(g, cache)
    save_cache(cache)
    OUT_HTML.write_text(render(data))
    n_days_load = sum(1 for v in data["load"]["ctl"] if v is not None)
    log("")
    log(f"  wrote {OUT_HTML}")
    log(f"  {len(data['table'])} activities in table · {n_days_load} days of load data · "
        f"{sum(1 for v in data['recovery']['hrv_weekly'] if v is not None)} days of HRV")
    print(OUT_HTML)


if __name__ == "__main__":
    main()
