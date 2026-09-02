# Single-file dashboard (original prototype)

> **This is the frozen, one-file version.** It's kept for the "just run one
> script" case and as the starting point the [`garmin_dashboard` package](../)
> grew out of. New work happens in [`../garmin_dashboard/`](../garmin_dashboard);
> this file is not kept in lockstep with it (CI only checks that it still
> compiles).

Everything — data fetching, HTML, CSS and JS — lives in `dashboard.py`. Running
it writes a self-contained `index.html` next to the script.

---

## Quick start

```bash
cd simple-garmin-dashboard
uv run dashboard.py       # fetch + build ./index.html
open index.html           # macOS
```

`uv` reads the inline script metadata (PEP 723) and installs the one dependency
(`garminconnect==0.3.2`) automatically. No `uv`? `pip install 'garminconnect==0.3.2'`
then `python dashboard.py`.

It never prompts for a password: it resumes the OAuth tokens cached at
`~/.garminconnect`. Get those once with the Garmin MCP's auth helper:

```bash
uvx --python 3.12 --from git+https://github.com/Taxuspt/garmin_mcp garmin-mcp-auth
```

A local `.dashboard_cache.json` makes repeat runs fast. Both it and `index.html`
embed personal health data and are gitignored.

---

## Configuration

Edit the `CONFIG` block at the top of `dashboard.py` directly — `RACES`
(name + `YYYY-MM-DD`) and the window knobs (`LOAD_WEEKS`, `RECOVERY_WEEKS`,
`MILEAGE_WEEKS`, `TABLE_DAYS`, `REFETCH_RECENT_DAYS`). The packaged version moves
all of this to `../config.toml`.

---

## What's on it

Race countdown · CTL/ATL/TSB training load · weekly volume + weekly time by sport
(Monday–Sunday buckets) · recovery (HRV / resting HR / sleep) · VO₂ max trend ·
recent-activities table · PRs and Garmin race predictions. Light/dark theme with
an Auto/Light/Dark toggle.

See the [top-level README](../README.md) for the architecture, the Garmin MCP
relationship, credits, and caveats — all of which apply here too.
