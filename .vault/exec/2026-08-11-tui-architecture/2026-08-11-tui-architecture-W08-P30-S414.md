---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:916f2d1e38573ea2e7ab95c1f78898d8c19e4896145bacf3d39ff3813f3e51c8'
step_id: 'S414'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Derive every workbench surface from one design language instead of per-screen values. OPERATOR REVIEW OF THE RENDERED FRAMES, 2026-09-04: spacing and colour are inconsistent and non-canonical across surfaces, and not all of the design derives from the same UX vocabulary -- screens were evidently styled against themselves rather than against a shared token table. The theme module already declares tokens; what is missing is that every surface spends them and nothing hard-codes a measure or a colour of its own. Audit the whole TUI stylesheet surface for literal values standing in for tokens, for tokens used inconsistently between screens that mean the same thing, and for the places where two screens express one concept differently.

## Scope

- `src/cadrumo/entrypoints/tui/components/theme.py and every screen stylesheet under src/cadrumo/entrypoints/tui/`

## Changes

- `M` `src/cadrumo/entrypoints/tui/devtools/home_candidates.py`
- `M` `src/cadrumo/entrypoints/tui/secret/registration.py`
- `verify:` `pytest -n0 -m '' src/cadrumo/entrypoints/tui/tests/test_theme.py` -> `pass`

## Notes

The two stylesheets still outside the token table are now inside it. Both
`home_candidates.py` CSS blocks went through `tokenised()`, which they had
never used, and their literal measures resolve to the scale: the panel box to
`tight`/`space-1`/`stack`, its corner to `cadrumo-radius`, its heading gap to
`stack`. `registration.py` already called `tokenised()` and simply hardcoded
three `margin-bottom: 1`, now `stack`.

Offenders went 11 -> 0 and the gate is green at 36 passed. Teeth re-proven by
restoring one literal `margin-bottom: 1` in `registration.py`; the gate named
that exact file and declaration, and the file was restored by copy.
