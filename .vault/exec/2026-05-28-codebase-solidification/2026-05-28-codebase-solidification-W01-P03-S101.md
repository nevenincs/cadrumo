---
step_id: S101
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P03.S101 — empty_identity_nif threading

## Outcome

Threaded `translated_message=tr("adapters.sede.errors.empty_identity_nif")` on both
`SedeNavigationError` raises for empty NIF in `_declarations.py`:

- `capture_filed_declaration_observation` (line ~916)
- `_capture_filed_declaration_observation_from_row` (line ~962)

Scaffolded `adapters.sede.errors.empty_identity_nif` via `python -m aeat.locales scaffold`
then set values in all four catalogues (es, en, ca, hu).

## Files touched

- `src/aeat/adapters/outbound/aeat/sede/_declarations.py`
- `src/aeat/locales/en.yml`
- `src/aeat/locales/es.yml`
- `src/aeat/locales/ca.yml`
- `src/aeat/locales/hu.yml`

## Verification

`python -m aeat.locales audit` clean on all four catalogues.
