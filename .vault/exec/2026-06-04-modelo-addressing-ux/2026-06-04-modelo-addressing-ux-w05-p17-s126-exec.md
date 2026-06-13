---
tags:
  - '#exec'
  - '#modelo-addressing-ux'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S126'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# `W05.P17.S126` Locale and translation guard coverage

Step scope: `src/aeat/locales`.

## Description

- Ran exact stale-guidance scan across shipped locale files.
- Ran locale parity, hardened error coverage, and placeholder parity guards.
- Fixed locale drift for row-validation keys so the locale catalogue remains in
  parity while stale casilla numeric keys are retired.

## Outcome

Locale stale-guidance scan returned no matches:

- `rg -n "work calculate <|work verify <|work file <|work revisions <|modelo export <|modelo reconcile <|app modelo work calculate %\\{|app modelo work revisions %\\{|app modelo work verify %\\{|app modelo export %\\{|copy/paste|copy and paste|raw ID|raw-id" src/aeat/locales/en.yml src/aeat/locales/es.yml src/aeat/locales/ca.yml src/aeat/locales/hu.yml`

Locale guard bundle passed:

- `.venv\Scripts\python.exe -m pytest -q src/aeat/locales/test_parity.py src/aeat/test_locale_coverage_hardened_errors.py src/aeat/core/i18n/test_placeholder_parity.py`
  passed `97` tests.

Ruff passed:

- `.venv\Scripts\ruff.exe check src/aeat/locales src/aeat/core/i18n src/aeat/test_locale_coverage_hardened_errors.py`

Locale drift corrected in the source files:

- Removed obsolete `cli.app.modelo.work.casilla_bare_numeric_ambiguous` and
  `cli.app.modelo.work.casilla_bare_numeric_unknown` locale leaves.
- Added live `cli.app.modelo.work.row_m184_share_sum_error` and
  `cli.app.modelo.work.row_m347_threshold_error` leaves with required placeholders
  in all shipped locale YAMLs.
