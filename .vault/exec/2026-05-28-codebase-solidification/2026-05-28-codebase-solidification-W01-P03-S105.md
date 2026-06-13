---
step_id: S105
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P03.S105 — profile diagnostics unset placeholder localization

## Outcome

Replaced the two hardcoded `'<unset>'` string literals in
`src/aeat/diagnostics/profile.py` with `tr('cli.diagnostics.profile.unset_placeholder')`:

- Line 112: `profile get` output path (value absent branch).
- Line 166: `profile unset` confirmation output.

Locale key `cli.diagnostics.profile.unset_placeholder` added to all four locales
(en: `<unset>`, es: `<no establecido>`, ca: `<no definit>`, hu: `<nincs beállítva>`).

## Files touched

- `src/aeat/diagnostics/profile.py`
- `src/aeat/locales/en.yml`, `es.yml`, `ca.yml`, `hu.yml`

## Verification

`uv run --no-sync pytest src/aeat/diagnostics/test_profile.py -q`
→ 9 passed.

Commit: `f71428dd0` + `078eb3976` (locales parity sweep).
