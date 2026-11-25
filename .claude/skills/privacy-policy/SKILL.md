---
name: privacy-policy
description: Generates a Google Play compliant privacy policy, data-deletion page and Play Console "Data safety" answers for a mobile game with the ppgen tool in C:\PrivacyPolicyGenrator. Use whenever the user asks for a privacy policy, "gizlilik politikası", "privacy policy URL", Data safety form answers, a data deletion URL, or says Play rejected the app for its privacy policy, for any Unity/Android game.
---

# Privacy policy with ppgen

Tool root: `C:\PrivacyPolicyGenrator` (run every command from there). Python 3.10+, `pip install -r requirements.txt`.
All commands accept `--json` for machine-readable output; exit code 0 = success, 1 = problems.

## Workflow
1. **Detect** (if the game is a Unity project):
   `python ppgen.py detect "<unity-project-path>" --write [--slug my-game]`
   Writes `apps/<slug>.yaml` with name, package, company and detected SDKs. If the file exists it is not overwritten
   (use `--force` only if the user agrees; otherwise edit its `sdks:` list).
   No Unity project → `python ppgen.py new <slug>` and fill the file by hand.
2. **Fill the config** `apps/<slug>.yaml`. Ask the user only for what you cannot find:
   - `developer.email` – always `help@waow.games` (the user's standing choice; already the scaffold default).
   - `audience.children` – is under-13 in the Play target audience?
   - `features.*` – accounts, IAP, consent tool (UMP / LevelPlay / MAX CMP), UGC.
   - Mediation: ask which ad networks are enabled in the LevelPlay/MAX dashboard; add each to `sdks:`.
   - `hosting.base_url` – GitHub Pages root, e.g. `https://<user>.github.io/<repo>` (inherited from other apps).
   SDK ids: `python ppgen.py sdks`. An SDK missing from the list → add an entry to `data/sdks.yaml`
   (copy a similar one, fill every field), then `python ppgen.py check-links`.
3. **Validate**: `python ppgen.py validate <slug>` – fix every `error`; tell the user about `warn` lines.
4. **Build**: `python ppgen.py build <slug>` → `docs/<slug>/index.html` (policy), `docs/<slug>/data-deletion.html`,
   `reports/<slug>-play-console.md` (exact Data safety / Ads / Advertising ID answers).
5. **Publish**: commit and push `docs/` (GitHub Pages serves `main` branch `/docs`). Ask before committing/pushing.
6. **Verify**: `python ppgen.py verify-live <slug>` – must be all OK before the URL goes into Play Console.
7. Give the user: the policy URL, the deletion URL, and the path of the Play Console report.

## Rules
- Never edit files in `docs/` by hand; change the YAML or templates and rebuild.
- The policy and the Data safety form must match: whenever SDKs change, rebuild and redo the form from the report.
- Do not claim the result is legal advice.
- Templates: `templates/*.j2`. SDK data: `data/sdks.yaml`. Rules: `ppgen/model.py::validate`.
