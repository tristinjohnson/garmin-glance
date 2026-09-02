"""Render :class:`DashboardData` to a single self-contained HTML string."""

from __future__ import annotations

from importlib.resources import files

from jinja2 import Environment, PackageLoader, select_autoescape

from .models import DashboardData

_env = Environment(
    loader=PackageLoader("garmin_dashboard", "templates"),
    autoescape=select_autoescape(["html", "j2"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


def _asset(name: str) -> str:
    return (files("garmin_dashboard.static") / name).read_text(encoding="utf-8")


def render(data: DashboardData, *, demo: bool = False) -> str:
    template = _env.get_template("dashboard.html.j2")
    return template.render(
        data=data.as_payload(),
        css=_asset("dashboard.css"),
        js=_asset("dashboard.js"),
        demo=demo,
    )
