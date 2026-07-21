---
tags:
  - '#exec'
  - '#retired-missing-stamp-bridge'
date: '2026-07-06'
modified: '2026-07-15'
step_id: 'S11'
related:
  - "[[2026-07-06-cross-period-prorrata-plan]]"
---

# make a divergent stamped_revision_id block the seed with a REGISTRY_REVISION_DIVERGENCE-class finding and a missing legacy stamp surface a non-blocking advisory, never silence (carried-observations-stamp-their-revision)

## Scope

- `src/aeat/application/prorrata_register/_seed.py`

## Description

- Add `ProrrataPriorDefinitivaSeedEvaluation` and `ProrrataSeedFinding` to carry seed outcomes plus operator-visible findings.
- Keep `seed_carried_prior_definitiva_entry` as a convenience wrapper over the evaluation surface.
- Return a blocking `registry_revision_divergence` finding and no seed when the stored `stamped_revision_id` diverges from the law-determined prior settlement revision.
- Return a non-blocking `missing_legacy_revision_stamp` advisory while still seeding when a legacy observation has no revision stamp.

## Outcome

- Clean stamped observations still seed with no findings.
- Divergent stamped observations are blocked: the evaluation returns no seed, `blocked=True`, and a `registry_revision_divergence` finding carrying the stamped and selected revision ids.
- Missing legacy stamps are represented as an advisory path in the evaluation contract and remain non-blocking.
- Scoped gates passed: `ruff check src/aeat/application/prorrata_register/_seed.py`, direct import smoke, real encrypted-repository smoke for clean and divergent stamped observations, and `pytest -q src/aeat/domain/prorrata_register/tests/test_prorrata_register.py src/aeat/adapters/persistence/profile/tests/test_prorrata_register_roundtrip.py src/aeat/application/modelo/tests/test_prorrata_regularizacion_advisory.py` (`27 passed`).

## Notes

- The missing-stamp path is implemented for legacy structural payloads; current persisted observations are schema-required to carry `stamped_revision_id`.
- The committed test expansion for happy path, divergence, and missing-stamp cases remains the dedicated `W02.P03.S13` row.
