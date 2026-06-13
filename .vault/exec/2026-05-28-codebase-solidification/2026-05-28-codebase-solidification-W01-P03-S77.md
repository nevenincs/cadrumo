---
step_id: S77
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P03.S77 — draft_id_not_found locale enrollment

## Outcome

Replaced the bare f-string `raise _bad(f"draft id {draft_id!r} not found")` at
`src/aeat/entrypoints/cli/_common.py:263` with
`raise _bad(tr("cli.common.errors.draft_id_not_found", draft_id=draft_id))`.
`tr` was already imported at line 11; no new import required.

Scaffolded the new key via `python -m aeat.locales scaffold` then set locale
text for all four catalogues:

- en: `Draft ID %{draft_id} not found`
- es: `ID de borrador %{draft_id} no encontrado`
- ca: `ID d'esborrany %{draft_id} no trobat`
- hu: `A(z) %{draft_id} azonosítójú piszkozat nem található`

## Files touched

- `src/aeat/entrypoints/cli/_common.py`
- `src/aeat/locales/en.yml`
- `src/aeat/locales/es.yml`
- `src/aeat/locales/ca.yml`
- `src/aeat/locales/hu.yml`

## Verification

`python -m aeat.locales audit` clean. `vault plan step check S77` applied.
