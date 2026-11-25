"""Detect app info and third-party SDKs in a Unity project."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

SENSITIVE_PERMISSIONS = {
    "android.permission.ACCESS_FINE_LOCATION": "precise_location",
    "android.permission.ACCESS_COARSE_LOCATION": "approx_location",
    "android.permission.CAMERA": None,
    "android.permission.RECORD_AUDIO": None,
    "android.permission.READ_CONTACTS": None,
    "android.permission.GET_ACCOUNTS": None,
    "android.permission.READ_PHONE_STATE": None,
    "android.permission.READ_EXTERNAL_STORAGE": None,
    "android.permission.READ_MEDIA_IMAGES": None,
    "android.permission.QUERY_ALL_PACKAGES": "installed_apps",
}
SKIP_DIRS = {"Library", "Temp", "Logs", "obj", "Build", "Builds", ".git", "UserSettings", "node_modules"}
TEXT_SUFFIXES = (".gradle", ".xml", ".properties")


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _scan_files(root: Path) -> list[Path]:
    """Dependency manifests (*Dependencies.xml), gradle templates and AndroidManifest files."""
    found = []
    for base in (root / "Assets", root / "Packages"):
        if not base.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
            for name in filenames:
                if name.endswith("Dependencies.xml") or name.endswith(".gradle") or name == "AndroidManifest.xml" \
                        or name.endswith(".gradle.properties"):
                    found.append(Path(dirpath) / name)
    return found


def project_info(root: Path) -> dict:
    text = _read(root / "ProjectSettings" / "ProjectSettings.asset")
    info = {"product_name": None, "company_name": None, "package": None}
    m = re.search(r"^\s*productName:\s*(.+)$", text, re.M)
    if m:
        info["product_name"] = m.group(1).strip().strip("'\"")
    m = re.search(r"^\s*companyName:\s*(.+)$", text, re.M)
    if m:
        info["company_name"] = m.group(1).strip().strip("'\"")
    m = re.search(r"applicationIdentifier:\s*\n((?:[ \t]+\S+:.*\n?)+)", text)
    if m:
        m2 = re.search(r"Android:\s*(\S+)", m.group(1))
        if m2:
            info["package"] = m2.group(1)
    return info


def detect(root: Path, sdks: dict) -> dict:
    root = Path(root)
    if not (root / "Assets").is_dir() or not (root / "ProjectSettings").is_dir():
        raise ValueError(f"{root} is not a Unity project (needs Assets/ and ProjectSettings/)")

    manifest_deps: dict = {}
    mpath = root / "Packages" / "manifest.json"
    if mpath.exists():
        try:
            manifest_deps = json.loads(_read(mpath)).get("dependencies", {})
        except json.JSONDecodeError:
            pass

    files = _scan_files(root)
    corpus = [(f, _read(f)) for f in files]

    found: dict[str, list[str]] = {}
    for sid, s in sdks.items():
        d = s.get("detect") or {}
        ev = []
        for p in d.get("packages") or []:
            if p in manifest_deps:
                ev.append(f"Packages/manifest.json: {p}")
        for rel in d.get("paths") or []:
            if (root / rel).exists():
                ev.append(f"path: {rel}")
        for pat in d.get("patterns") or []:
            rx = re.compile(pat, re.I)
            for f, txt in corpus:
                if rx.search(txt):
                    ev.append(f"{f.relative_to(root).as_posix()}: /{pat}/")
                    break
        if ev:
            found[sid] = ev

    permissions = set()
    for f, txt in corpus:
        if f.name == "AndroidManifest.xml":
            permissions.update(re.findall(r'uses-permission[^>]*android:name="([^"]+)"', txt))
    sensitive = sorted(p for p in permissions if p in SENSITIVE_PERMISSIONS)

    notes = []
    if any(sdks[s]["category"] in ("advertising", "mediation") for s in found) and \
            "com.google.android.gms.permission.AD_ID" not in permissions:
        notes.append("Ad SDKs found: they normally add com.google.android.gms.permission.AD_ID at build time. "
                     "In Play Console > App content > Advertising ID answer 'Yes'.")
    if "levelplay" in found or "applovin" in found:
        notes.append("Mediation found: also add every *network adapter* you enabled in the mediation dashboard "
                     "(detected adapters are listed above; dashboard-only networks are invisible to the scan).")

    return {
        "project": str(root),
        **project_info(root),
        "sdks": found,
        "sensitive_permissions": sensitive,
        "suggested_own_data": sorted({SENSITIVE_PERMISSIONS[p] for p in sensitive if SENSITIVE_PERMISSIONS[p]}),
        "notes": notes,
    }
