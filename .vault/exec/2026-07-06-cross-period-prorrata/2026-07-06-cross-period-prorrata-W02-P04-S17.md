---
tags:
  - '#exec'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-17'
step_id: 'S17'
related:
  - "[[2026-07-06-cross-period-prorrata-plan]]"
---

# surface a BLOCKING divergence finding when a carried_prior_definitiva entry contradicts the prior observation, and an informational notice naming the provenance when an aeat_autorizada or inicio_actividad entry legitimately differs from the prior definitive (never silence)

## Scope

- `src/aeat/application/prorrata_register/_seed.py`

## Description

- Add `cross_check_prorrata_entry_against_prior_observation` to compare a register entry with the resolved prior definitive observation.
- Return a blocking `observation_revision_value_divergence` finding when a carried entry's percentage or source observation identity contradicts the prior observation.
- Return a non-blocking `regulated_prorrata_override_difference` notice when an AEAT-authorised or inicio entry legitimately differs from the prior definitive.
- Preserve existing seed findings, including missing legacy stamp advisories and revision-divergence blockers.

## Outcome

`W02.P04.S17` is implemented. The seed module now exposes the cross-check surface needed by the next test row: carried entries must match the prior observation, while regulated art. 105.Dos/Tres overrides differ visibly but do not block.

Verification:

- `uv run --no-sync ruff check src\aeat\application\prorrata_register\_seed.py`
- `uv run --no-sync pytest -q src\aeat\application\prorrata_register\tests\test_seed.py`

## Notes

No mocks, skips, xfails, new resolver convention, or new binding source kind were introduced. The committed cross-check assertions remain assigned to `W02.P04.S18`.
