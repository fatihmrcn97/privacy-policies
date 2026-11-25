"""Loading, validating and enriching app configs."""
from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
APPS_DIR = ROOT / "apps"
DATA_DIR = ROOT / "data"
DOCS_DIR = ROOT / "docs"
REPORTS_DIR = ROOT / "reports"
TEMPLATES_DIR = ROOT / "templates"

# Google Play Data safety vocabulary: id -> (category, type label, plain-language description)
DATA_TYPES: dict[str, tuple[str, str, str]] = {
    "approx_location": ("Location", "Approximate location",
                        "approximate location (country/region derived from your IP address)"),
    "precise_location": ("Location", "Precise location", "precise GPS location"),
    "name": ("Personal info", "Name", "your name or display/gamer name"),
    "email": ("Personal info", "Email address", "your email address"),
    "user_ids": ("Personal info", "User IDs", "account or player identifiers"),
    "purchase_history": ("Financial info", "Purchase history",
                         "in-app purchase history (items bought, price, time); no card details"),
    "app_interactions": ("App activity", "App interactions",
                         "how you use the game (levels played, sessions, taps on ads, feature use)"),
    "user_content": ("App activity", "Other user-generated content", "content you create or send in the game"),
    "installed_apps": ("App activity", "Installed apps", "information about other installed apps"),
    "crash_logs": ("App info and performance", "Crash logs", "crash logs"),
    "diagnostics": ("App info and performance", "Diagnostics",
                    "diagnostic data (load times, battery/memory state, errors)"),
    "other_performance": ("App info and performance", "Other app performance data", "other performance data"),
    "device_ids": ("Device or other IDs", "Device or other IDs",
                   "device identifiers such as the Android Advertising ID, app set ID or an install ID"),
}
CATEGORY_ORDER = ["Location", "Personal info", "Financial info", "App activity",
                  "App info and performance", "Device or other IDs"]

PURPOSES: dict[str, str] = {
    "app_functionality": "App functionality",
    "analytics": "Analytics",
    "developer_communications": "Developer communications",
    "advertising": "Advertising or marketing",
    "fraud_prevention": "Fraud prevention, security, and compliance",
    "personalization": "Personalization",
    "account_management": "Account management",
}

AD_CATEGORIES = {"advertising", "mediation"}
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
PACKAGE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(\.[A-Za-z][A-Za-z0-9_]*)+$")
SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def load_sdks() -> dict:
    with open(DATA_DIR / "sdks.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def app_path(slug: str) -> Path:
    return APPS_DIR / f"{slug}.yaml"


def list_slugs() -> list[str]:
    return sorted(p.stem for p in APPS_DIR.glob("*.yaml") if not p.stem.startswith("_"))


def load_app(slug: str) -> dict:
    path = app_path(slug)
    if not path.exists():
        raise FileNotFoundError(f"apps/{slug}.yaml not found (run `python ppgen.py new {slug}`)")
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    cfg["slug"] = slug
    return cfg


@dataclass
class Result:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _get(cfg: dict, dotted: str, default=None):
    cur = cfg
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def validate(cfg: dict, sdks: dict) -> Result:
    r = Result()
    slug = cfg.get("slug", "")
    if not SLUG_RE.match(slug):
        r.errors.append(f"file name '{slug}' must be lowercase-kebab-case (it becomes the URL path)")

    for key in ["app.name", "app.package", "developer.name", "developer.email", "policy.effective_date"]:
        val = _get(cfg, key)
        if val in (None, "") or (isinstance(val, str) and ("TODO" in val or "CHANGE" in val)):
            r.errors.append(f"{key} is required (currently {val!r})")

    pkg = _get(cfg, "app.package")
    if pkg and not PACKAGE_RE.match(str(pkg)):
        r.errors.append(f"app.package '{pkg}' is not a valid Android package name")
    email = _get(cfg, "developer.email")
    if email and not EMAIL_RE.match(str(email)):
        r.errors.append(f"developer.email '{email}' is not a valid email address")
    eff = _get(cfg, "policy.effective_date")
    if eff and not isinstance(eff, _dt.date):
        try:
            _dt.date.fromisoformat(str(eff))
        except ValueError:
            r.errors.append(f"policy.effective_date '{eff}' must be YYYY-MM-DD")

    base = _get(cfg, "hosting.base_url")
    if not base:
        r.warnings.append("hosting.base_url is empty: the report cannot print the final Play Console URLs")
    elif "TODO" in str(base):
        r.errors.append("hosting.base_url still contains TODO: set it to your GitHub Pages URL")
    elif not str(base).startswith("https://"):
        r.errors.append("hosting.base_url must start with https:// (Play needs a public HTTPS URL)")

    ids = cfg.get("sdks") or []
    if not isinstance(ids, list):
        r.errors.append("sdks must be a list of SDK ids")
        ids = []
    unknown = [i for i in ids if i not in sdks]
    for i in unknown:
        r.errors.append(f"unknown SDK id '{i}' (see `python ppgen.py sdks`, or add it to data/sdks.yaml)")
    if len(set(ids)) != len(ids):
        r.warnings.append("sdks contains duplicates")
    known = [sdks[i] for i in ids if i in sdks]

    for n, item in enumerate(cfg.get("own_data") or []):
        t = item.get("type")
        if t not in DATA_TYPES:
            r.errors.append(f"own_data[{n}].type '{t}' unknown; valid: {', '.join(DATA_TYPES)}")
        for p in item.get("purposes") or []:
            if p not in PURPOSES:
                r.errors.append(f"own_data[{n}] purpose '{p}' unknown; valid: {', '.join(PURPOSES)}")
        if not item.get("purposes"):
            r.errors.append(f"own_data[{n}] needs at least one purpose")
        if "TODO" in str(item.get("reason", "")):
            r.errors.append(f"own_data[{n}].reason still contains TODO")
        if not item.get("reason"):
            r.errors.append(f"own_data[{n}] needs a 'reason' sentence (shown in the policy)")

    has_ads = any(s["category"] in AD_CATEGORIES for s in known)
    children = bool(_get(cfg, "audience.children", False))
    age_gate = bool(_get(cfg, "audience.age_gate", False))
    personalized = bool(_get(cfg, "features.personalized_ads", has_ads))

    if children:
        if has_ads and personalized and not age_gate:
            r.errors.append("audience.children is true: Families policy forbids personalized ads to children. "
                            "Set features.personalized_ads: false, or audience.age_gate: true if you use a neutral age screen")
        for i in ids:
            s = sdks.get(i)
            if s and s["category"] in AD_CATEGORIES and s.get("families_listed") is not True:
                r.warnings.append(f"'{i}' is not confirmed on Google's Families Self-Certified Ads SDK list; "
                                  "only certified ad SDKs may serve ads to children")
        if any(i in ("facebook_sdk",) for i in ids):
            r.warnings.append("facebook_sdk in a children-directed app is commonly rejected; remove it if possible")

    if has_ads and not _get(cfg, "features.consent_tool"):
        r.warnings.append("ads are used but features.consent_tool is empty: EEA/UK users need a Google-certified CMP "
                          "(e.g. Google UMP / AdMob Privacy & messaging, or LevelPlay/MAX built-in CMP)")

    if bool(_get(cfg, "features.accounts", False)) and not _get(cfg, "features.account_deletion_in_app"):
        r.warnings.append("features.accounts is true: Play also wants in-app account deletion; set "
                          "features.account_deletion_in_app: true once the game has a delete-account button")

    if not ids and not cfg.get("own_data"):
        r.warnings.append("no SDKs and no own_data: the policy will state the game collects no personal data. "
                          "Double-check with `python ppgen.py detect <unity-project>`")
    return r


def enrich(cfg: dict, sdks: dict) -> dict:
    """Return the template context."""
    ids = [i for i in (cfg.get("sdks") or []) if i in sdks]
    used = [dict(sdks[i], id=i) for i in ids]
    has_ads = any(s["category"] in AD_CATEGORIES for s in used)
    has_iap = "google_play_billing" in ids or bool(_get(cfg, "features.in_app_purchases", False))

    rows: dict[str, dict] = {}

    def add(type_id, source, shared, purposes, optional):
        cat, label, desc = DATA_TYPES[type_id]
        row = rows.setdefault(type_id, {"id": type_id, "category": cat, "label": label, "desc": desc,
                                        "sources": [], "shared": False, "purposes": set(),
                                        "shared_purposes": set(), "optional": True})
        row["sources"].append(source)
        row["shared"] = row["shared"] or shared
        row["purposes"].update(purposes)
        if shared:
            row["shared_purposes"].update(purposes)
        row["optional"] = row["optional"] and optional

    for s in used:
        for t in s.get("collects", []):
            add(t, s["name"], bool(s.get("shared")), s.get("purposes", []), False)
    for item in cfg.get("own_data") or []:
        add(item["type"], cfg["developer"]["name"], bool(item.get("shared", False)),
            item.get("purposes", []), bool(item.get("optional", True)))

    data_rows = sorted(rows.values(), key=lambda r: (CATEGORY_ORDER.index(r["category"]), r["label"]))
    for r in data_rows:
        r["purpose_labels"] = [PURPOSES[p] for p in PURPOSES if p in r["purposes"]]
        r["shared_purpose_labels"] = [PURPOSES[p] for p in PURPOSES if p in r["shared_purposes"]]

    base = (_get(cfg, "hosting.base_url") or "").rstrip("/")
    slug = cfg["slug"]
    eff = _get(cfg, "policy.effective_date")
    if isinstance(eff, str):
        eff = _dt.date.fromisoformat(eff)

    personalized = bool(_get(cfg, "features.personalized_ads", has_ads)) and has_ads
    ctx = dict(cfg)
    ctx.update(
        sdk_list=used,
        ad_sdks=[s for s in used if s["category"] in AD_CATEGORIES],
        has_ads=has_ads,
        has_iap=has_iap,
        uses_ad_id=any(s.get("uses_ad_id") for s in used),
        uses_analytics=any("analytics" in r["purposes"] for r in data_rows),
        personalized_ads=personalized,
        data_rows=data_rows,
        collects_anything=bool(data_rows),
        shares_anything=any(r["shared"] for r in data_rows),
        effective_date=eff,
        effective_date_text=eff.strftime("%B %d, %Y").replace(" 0", " ") if eff else "",
        policy_url=f"{base}/{slug}/" if base else f"<base_url>/{slug}/",
        deletion_url=f"{base}/{slug}/data-deletion.html" if base else f"<base_url>/{slug}/data-deletion.html",
        children=bool(_get(cfg, "audience.children", False)),
        country=str(_get(cfg, "developer.country", "") or "").upper(),
        f=cfg.get("features") or {},
    )
    return ctx
