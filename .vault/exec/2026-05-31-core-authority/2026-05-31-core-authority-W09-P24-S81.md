---
tags:
  - '#exec'
  - '#core-authority'
step_id: S81
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
---

# core-authority W09.P24.S81 - domain-to-entrypoints edge removal

## Outcome

Identified all 5 domain-to-entrypoints import edges (MIGRATE-004, RELOC-030). All 5 were in
`domain/profile/test_deduccion_maternidad_0611.py`, all importing `_compute_deduccion_maternidad_0611`
from `aeat.entrypoints.cli._modelo`.

**Fixed (5 edges):**
- Extracted `_compute_deduccion_maternidad_0611` (pure Art. 81 LIRPF arithmetic) from
  `entrypoints/cli/_modelo.py` to new `domain/profile/_deduccion_maternidad.py`.
- Renamed to `compute_deduccion_maternidad_0611` (public, no leading underscore) at the canonical domain location.
- `_modelo.py` now imports the function from domain under its original private alias, so all
  call sites in the entrypoint are unchanged.
- The test file now imports from `aeat.domain.profile._deduccion_maternidad` — 0 entrypoints imports remain.

## Commit

`5102d9b5f` — refactor(domain): W09.P24.S81 - extract compute_deduccion_maternidad_0611 to domain/profile

## Files touched

- `src/aeat/domain/profile/_deduccion_maternidad.py` — new module (pure domain arithmetic)
- `src/aeat/domain/profile/test_deduccion_maternidad_0611.py` — updated 5 lazy imports to domain location
- `src/aeat/entrypoints/cli/_modelo.py` — imports from domain; local definition removed

## Verification

22 tests pass in test_deduccion_maternidad_0611.py. All 5 domain-to-entrypoints edges eliminated.
