---
tags:
  - '#exec'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:ae29982820782e11805788a2d6283e6b533d73dd5d33ab3b565134312821dcdf'
step_id: 'S10'
related:
  - "[[2026-07-06-cross-period-prorrata-plan]]"
---

# implement the seed function: resolve the prior settlement revision via select_revision(M303, ejercicio-1, settlement period), read the iva.prorrata-porcentaje observation, and re-confirm its stamped_revision_id before seeding the carried_prior_definitiva entry

## Scope

- `src/aeat/application/prorrata_register/_seed.py`

## Description

- Add `seed_carried_prior_definitiva_entry` and `ProrrataPriorDefinitivaSeed` in `src/aeat/application/prorrata_register/_seed.py`.
- Scan the real `CalculationObservationRepository` for prior-year Modelo 303 settlement observations carrying `iva.prorrata-porcentaje`.
- Resolve the law-determined prior settlement revision with `select_revision` for the source `(M303, ejercicio - 1, period)` before trusting the observation.
- Build a `carried_prior_definitiva` `ProrrataRegisterEntry` only when the stored `stamped_revision_id` matches that selected revision.

## Outcome

- Seed happy path verified through a real encrypted observation repository: a stored 2025 M303 4T observation with the current stamped revision seeds the 2026 register entry at percentage `87`.
- Divergent stamp refusal verified through the same repository path: a stored 2025 M303 4T observation stamped with `not-the-law-determined-revision` does not seed an entry.
- Scoped gates passed: `ruff check src/aeat/application/prorrata_register/_seed.py`, direct import smoke, and `pytest -q src/aeat/domain/prorrata_register/tests/test_prorrata_register.py src/aeat/adapters/persistence/profile/tests/test_prorrata_register_roundtrip.py src/aeat/application/modelo/tests/test_prorrata_regularizacion_advisory.py` (`27 passed`).

## Notes

- This step deliberately leaves the operator-facing divergent-stamp blocker and missing-stamp advisory to `W02.P03.S11`.
- This step deliberately leaves permanent `source_observation_ref` recording on the seeded entry to `W02.P03.S12`.
- No new binding source kind, resolver convention, validator convention, or plan scope was introduced.
