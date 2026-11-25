# ppgen – agent notes

Google Play privacy policy generator for mobile games. Full workflow: `.claude/skills/privacy-policy/SKILL.md`.

- One game = one `apps/<slug>.yaml` → `python ppgen.py build <slug>` → `docs/<slug>/` (served by GitHub Pages) +
  `reports/<slug>-play-console.md`.
- Commands: `sdks`, `new`, `detect`, `validate`, `build`, `verify-live`, `check-links`; add `--json` for JSON output.
- `apps/_*.yaml` are examples and are never built.
- Never hand-edit `docs/`; it is generated. Edit `templates/*.j2`, `data/sdks.yaml` or `ppgen/*.py` instead.
- After changing templates or rules, rebuild all apps: `python ppgen.py build --all`.
- Privacy contact email is always help@waow.games. Never claim the output is legal advice.
