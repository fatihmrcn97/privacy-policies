"""ppgen command line. Every command supports --json for machine-readable output."""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from . import model
from .detect import detect
from .render import build_app, build_index

UA = "Mozilla/5.0 (compatible; ppgen-linkcheck/1.0)"


def _out(args, data, text: str):
    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False, default=str))
    else:
        print(text)


def _slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "my-game"


def _scaffold(slug: str, info: dict | None = None, sdk_ids=None, own_data=None, base_url: str = "") -> str:
    env = Environment(loader=FileSystemLoader(str(model.TEMPLATES_DIR)), trim_blocks=True, lstrip_blocks=True)
    info = info or {}
    return env.get_template("app.yaml.j2").render(
        slug=slug,
        name=info.get("product_name") or "TODO Game Name",
        package=info.get("package") or "com.TODO.game",
        developer=info.get("company_name") or "TODO Developer Name",
        today=_dt.date.today().isoformat(),
        sdks=sdk_ids or [],
        own_data=own_data or [],
        base_url=base_url,
        all_sdks=model.load_sdks(),
    )


def _default_base_url() -> str:
    """Reuse hosting.base_url from any existing app so new apps inherit it."""
    for slug in model.list_slugs():
        try:
            b = (model.load_app(slug).get("hosting") or {}).get("base_url")
            if b and "TODO" not in b:
                return b
        except Exception:
            pass
    return ""


# ---------------------------------------------------------------- commands
def cmd_sdks(args):
    sdks = model.load_sdks()
    rows = [{"id": k, "name": v["name"], "category": v["category"], "families_listed": v.get("families_listed")}
            for k, v in sdks.items()]
    text = "\n".join(f"{r['id']:<24} {r['category']:<12} {r['name']}" for r in rows)
    _out(args, rows, text)
    return 0


def cmd_new(args):
    slug = args.slug
    path = model.app_path(slug)
    if path.exists() and not args.force:
        _out(args, {"ok": False, "error": "exists", "path": str(path)}, f"apps/{slug}.yaml already exists (use --force)")
        return 1
    model.APPS_DIR.mkdir(exist_ok=True)
    path.write_text(_scaffold(slug, base_url=_default_base_url()), encoding="utf-8", newline="\n")
    _out(args, {"ok": True, "path": str(path)}, f"created apps/{slug}.yaml - fill the TODO fields, then run validate")
    return 0


def cmd_detect(args):
    sdks = model.load_sdks()
    try:
        res = detect(Path(args.project), sdks)
    except ValueError as e:
        _out(args, {"ok": False, "error": str(e)}, f"error: {e}")
        return 1
    slug = args.slug or _slugify(res.get("product_name") or Path(args.project).name)
    res["slug"] = slug
    lines = [f"Unity project : {res['project']}",
             f"product name  : {res['product_name']}",
             f"company name  : {res['company_name']}",
             f"package       : {res['package']}",
             "SDKs found    :"]
    for sid, ev in res["sdks"].items():
        lines.append(f"  - {sid:<22} ({ev[0]}{' +%d more' % (len(ev) - 1) if len(ev) > 1 else ''})")
    if not res["sdks"]:
        lines.append("  (none)")
    if res["sensitive_permissions"]:
        lines.append("sensitive permissions: " + ", ".join(res["sensitive_permissions"]))
    lines += [f"note: {n}" for n in res["notes"]]

    if args.write:
        path = model.app_path(slug)
        if path.exists() and not args.force:
            res["written"] = None
            lines.append(f"apps/{slug}.yaml exists; not overwritten (use --force, or edit its sdks: list by hand)")
        else:
            own = [{"type": t, "purposes": ["app_functionality"],
                    "reason": "TODO explain why the game needs this permission"} for t in res["suggested_own_data"]]
            model.APPS_DIR.mkdir(exist_ok=True)
            path.write_text(_scaffold(slug, res, list(res["sdks"]), own, _default_base_url()),
                            encoding="utf-8", newline="\n")
            res["written"] = str(path)
            lines.append(f"wrote apps/{slug}.yaml - fill the remaining TODO fields, then run validate")
    _out(args, res, "\n".join(lines))
    return 0


def _targets(args) -> list[str]:
    if getattr(args, "all", False) or not args.slug:
        return model.list_slugs()
    return [args.slug]


def cmd_validate(args):
    sdks = model.load_sdks()
    results, code = [], 0
    for slug in _targets(args):
        try:
            cfg = model.load_app(slug)
            r = model.validate(cfg, sdks)
            results.append({"slug": slug, "ok": r.ok, "errors": r.errors, "warnings": r.warnings})
        except Exception as e:  # noqa: BLE001
            results.append({"slug": slug, "ok": False, "errors": [str(e)], "warnings": []})
        code |= 0 if results[-1]["ok"] else 1
    lines = []
    for r in results:
        lines.append(f"[{'OK' if r['ok'] else 'FAIL'}] {r['slug']}")
        lines += [f"   error: {e}" for e in r["errors"]]
        lines += [f"   warn : {w}" for w in r["warnings"]]
    if not results:
        lines.append("no apps found in apps/ (run `python ppgen.py new <slug>`)")
    _out(args, results, "\n".join(lines))
    return code


def cmd_build(args):
    sdks = model.load_sdks()
    built, failed, code = [], [], 0
    wanted = set(_targets(args))
    index_entries = []
    for slug in model.list_slugs():
        try:
            cfg = model.load_app(slug)
            r = model.validate(cfg, sdks)
        except Exception as e:  # noqa: BLE001
            if slug in wanted:
                failed.append({"slug": slug, "errors": [str(e)]})
                code = 1
            continue
        if not r.ok:
            if slug in wanted:
                failed.append({"slug": slug, "errors": r.errors})
                code = 1
            continue
        ctx = model.enrich(cfg, sdks)
        entry = {"slug": slug, "app_name": cfg["app"]["name"], "developer": cfg["developer"]["name"],
                 "policy_url": ctx["policy_url"]}
        if slug in wanted:
            res = build_app(cfg, sdks)
            res["warnings"] = r.warnings
            if res["self_check"]:
                code = 1
            built.append(res)
        index_entries.append(entry)
    build_index(index_entries)

    lines = []
    for b in built:
        lines.append(f"[built] {b['slug']}")
        lines.append(f"   policy URL  : {b['policy_url']}")
        lines.append(f"   deletion URL: {b['deletion_url']}")
        lines.append(f"   Play Console answers: reports/{b['slug']}-play-console.md")
        lines += [f"   SELF-CHECK FAILED: {p}" for p in b["self_check"]]
        lines += [f"   warn: {w}" for w in b["warnings"]]
    for f in failed:
        lines.append(f"[FAIL] {f['slug']}")
        lines += [f"   error: {e}" for e in f["errors"]]
    if not wanted:
        lines.append("no apps found in apps/")
    _out(args, {"built": built, "failed": failed}, "\n".join(lines))
    return code


def _fetch(url: str, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(400_000).decode("utf-8", errors="ignore")
            return resp.status, resp.headers.get("Content-Type", ""), resp.geturl(), body
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Content-Type", "") if e.headers else "", url, ""
    except Exception as e:  # noqa: BLE001
        return None, "", url, str(e)


def cmd_check_links(args):
    sdks = model.load_sdks()
    results = []
    for sid, s in sdks.items():
        for key in ("privacy_url", "partner_url", "data_safety_url"):
            url = s.get(key)
            if not url:
                continue
            status, _, final, err = _fetch(url)
            ok = status is not None and status < 400
            # some sites block bots (403/429) but work in a browser
            results.append({"sdk": sid, "field": key, "url": url, "status": status, "final_url": final,
                            "ok": ok, "error": None if status else err})
    bad = [r for r in results if not r["ok"]]
    lines = [f"{'OK ' if r['ok'] else 'BAD'} {r['status']!s:>4}  {r['sdk']:<22} {r['field']:<16} {r['url']}"
             for r in results]
    lines.append(f"\n{len(results) - len(bad)}/{len(results)} links OK"
                 + (" (403/429 often means bot-blocking; open those in a browser)" if bad else ""))
    _out(args, results, "\n".join(lines))
    return 1 if bad else 0


def cmd_verify_live(args):
    """Check the deployed page the way a Play reviewer would reach it."""
    sdks = model.load_sdks()
    results, code = [], 0
    for slug in _targets(args):
        cfg = model.load_app(slug)
        ctx = model.enrich(cfg, sdks)
        checks = []
        for label, url in (("policy", ctx["policy_url"]), ("deletion", ctx["deletion_url"])):
            status, ctype, final, body = _fetch(url)
            c = {"page": label, "url": url, "status": status, "content_type": ctype, "problems": []}
            if status != 200:
                c["problems"].append(f"HTTP {status} - page is not publicly reachable yet")
            else:
                if "text/html" not in ctype:
                    c["problems"].append(f"content-type is {ctype!r}, Play wants an HTML page")
                if label == "policy":
                    for s in ("Privacy Policy", cfg["app"]["name"], cfg["app"]["package"], cfg["developer"]["email"]):
                        if s not in body:
                            c["problems"].append(f"live page does not contain {s!r} (old deploy?)")
                if not final.startswith("https://"):
                    c["problems"].append("final URL is not HTTPS")
            checks.append(c)
            if c["problems"]:
                code = 1
        results.append({"slug": slug, "checks": checks})
    lines = []
    for r in results:
        for c in r["checks"]:
            lines.append(f"[{'OK' if not c['problems'] else 'FAIL'}] {r['slug']} {c['page']}: {c['url']}")
            lines += [f"   - {p}" for p in c["problems"]]
    _out(args, results, "\n".join(lines))
    return code


def cmd_publish(args):
    """Commit apps/, docs/, reports/, push, then wait until the live pages serve the new build."""
    import subprocess
    import time

    def git(*a):
        return subprocess.run(["git", *a], cwd=model.ROOT, capture_output=True, text=True)

    git("add", "-A")
    msg = args.message or "Update privacy policies"
    c = git("commit", "-m", msg)
    committed = c.returncode == 0
    p = git("push")
    if p.returncode != 0:
        _out(args, {"ok": False, "error": p.stderr}, f"git push failed:\n{p.stderr}")
        return 1
    if args.no_wait:
        _out(args, {"ok": True, "committed": committed}, "pushed (not waiting for Pages)")
        return 0
    import contextlib
    import io

    if not model.list_slugs():
        _out(args, {"ok": True, "committed": committed}, "pushed; no apps to verify yet")
        return 0
    deadline = time.time() + args.timeout
    while time.time() < deadline:  # GitHub Pages usually redeploys within 1-2 minutes
        with contextlib.redirect_stdout(io.StringIO()):
            if cmd_verify_live(argparse.Namespace(slug=None, all=True, json=True)) == 0:
                break
        time.sleep(15)
    return cmd_verify_live(argparse.Namespace(slug=None, all=True, json=args.json))


def main(argv=None):
    p = argparse.ArgumentParser(prog="ppgen", description="Google Play privacy policy generator")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("sdks", help="list supported SDK ids").set_defaults(fn=cmd_sdks)

    s = sub.add_parser("new", help="create apps/<slug>.yaml from the template")
    s.add_argument("slug")
    s.add_argument("--force", action="store_true")
    s.set_defaults(fn=cmd_new)

    s = sub.add_parser("detect", help="scan a Unity project for app info and SDKs")
    s.add_argument("project", help="path to the Unity project root")
    s.add_argument("--slug", help="config name (default: from productName)")
    s.add_argument("--write", action="store_true", help="write apps/<slug>.yaml")
    s.add_argument("--force", action="store_true", help="overwrite an existing config")
    s.set_defaults(fn=cmd_detect)

    for name, fn, hlp in (("validate", cmd_validate, "check configs against Play rules"),
                          ("build", cmd_build, "render docs/<slug>/ pages and the Play Console report"),
                          ("verify-live", cmd_verify_live, "check the published URLs are reachable and current")):
        s = sub.add_parser(name, help=hlp)
        s.add_argument("slug", nargs="?", help="app slug (default: all)")
        s.add_argument("--all", action="store_true")
        s.set_defaults(fn=fn)

    sub.add_parser("check-links", help="check every SDK URL in data/sdks.yaml").set_defaults(fn=cmd_check_links)

    s = sub.add_parser("publish", help="git commit + push, then wait until the live pages are up to date")
    s.add_argument("-m", "--message", help="commit message")
    s.add_argument("--timeout", type=int, default=300, help="seconds to wait for GitHub Pages (default 300)")
    s.add_argument("--no-wait", action="store_true")
    s.set_defaults(fn=cmd_publish)

    argv = list(sys.argv[1:] if argv is None else argv)
    want_json = "--json" in argv  # accept --json anywhere, not only before the subcommand
    argv = [a for a in argv if a != "--json"]
    args = p.parse_args(argv)
    args.json = want_json
    if want_json or sys.stdout.encoding.lower().replace("-", "") != "utf8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except AttributeError:
            pass
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
