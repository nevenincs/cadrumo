---
step_id: S97
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W01.P03.S97 — route missing_required_casilla message through tr()

## Outcome

`_missing_required_casilla_finding` in `src/aeat/application/modelo/_actions.py`
now routes `message=` through
`tr("application.modelo.findings.missing_required_casilla", casilla_id=casilla_id)`
replacing the hardcoded English f-string. The locale key was confirmed present in
all four locale files (es, en, ca, hu) via `python -m aeat.locales audit`.

Production code change landed in commit `e5e3c630e` by a parallel agent;
locale scaffold and audit confirmed clean.

## Files touched

- `src/aeat/application/modelo/_actions.py` (message= route — in HEAD)

## Verification

`vault plan step check S97` applied. Locale audit: all four locales ok.
