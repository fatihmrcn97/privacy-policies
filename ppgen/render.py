"""Render policy pages, data-deletion page, Play Console report and the site index."""
from __future__ import annotations

import datetime as _dt
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, ChainableUndefined, select_autoescape

from .model import DOCS_DIR, REPORTS_DIR, TEMPLATES_DIR, enrich

_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html", "j2"], default_for_string=False),
    undefined=ChainableUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
)
_md_env = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=False,
    undefined=ChainableUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
)


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def self_check(html: str, ctx: dict) -> list[str]:
    """Things a Play reviewer looks for on the page itself."""
    problems = []
    must = ["Privacy Policy", ctx["app"]["name"], ctx["developer"]["name"], ctx["developer"]["email"]]
    for s in must:
        if s not in html:
            problems.append(f"rendered page does not contain {s!r}")
    for s in ctx["sdk_list"]:
        if s["privacy_url"] not in html:
            problems.append(f"rendered page is missing the privacy link of {s['name']}")
    return problems


def build_app(cfg: dict, sdks: dict) -> dict:
    ctx = enrich(cfg, sdks)
    ctx["generated_at"] = _dt.date.today().isoformat()
    slug = cfg["slug"]
    out = DOCS_DIR / slug

    policy_html = _env.get_template("privacy.html.j2").render(**ctx)
    deletion_html = _env.get_template("data-deletion.html.j2").render(**ctx)
    report_md = _md_env.get_template("play-console.md.j2").render(**ctx)

    problems = self_check(policy_html, ctx)
    files = [
        _write(out / "index.html", policy_html),
        _write(out / "data-deletion.html", deletion_html),
        _write(REPORTS_DIR / f"{slug}-play-console.md", report_md),
    ]
    return {"slug": slug, "policy_url": ctx["policy_url"], "deletion_url": ctx["deletion_url"],
            "files": [str(p) for p in files], "self_check": problems,
            "app_name": cfg["app"]["name"], "developer": cfg["developer"]["name"]}


def build_index(built: list[dict]) -> Path:
    DOCS_DIR.mkdir(exist_ok=True)
    _write(DOCS_DIR / ".nojekyll", "")
    # keep entries for apps that exist in docs/ even if not rebuilt this run
    html = _env.get_template("index.html.j2").render(apps=sorted(built, key=lambda b: b["app_name"].lower()))
    return _write(DOCS_DIR / "index.html", html)
