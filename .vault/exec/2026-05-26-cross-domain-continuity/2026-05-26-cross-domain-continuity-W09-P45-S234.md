---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-02'
modified: '2026-07-17'
body_hash: 'sha256:d5539c206007d8cbba3ce4b71c2033600f1bc092ec085b18b1a1f0426375216f'
step_id: 'S234'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# R7-ANNA-D3 fix iva.regime defaulting to GENERAL for entity_type=natural_person profiles without actividad_economica

## Scope

- `field should remain unset or marked no_aplica until user opts in`
- `misleading for salaried-only profiles`
- `src/aeat/application/wizard/`

## Description

- Gate the `iva-regime` wizard question to legal entities, attribution entities, and natural persons that declare `actividad_economica`.
- Centralise the conditional IVA-regime requirement in profile completeness policy.
- Let profile validation and key-readiness projection omit `iva.regime` for natural-person profiles without economic-activity income.
- Mark non-enrolled natural-person runtime projection as `NO_APLICA` instead of silently defaulting to `GENERAL`.
- Keep explicit IVA declarations for pure-landlord profiles and keep `GENERAL` defaults for legal entities, attribution entities, and economic-activity natural persons.
- Derive operator-facing `--iva-regime` choices from the wizard question choices so the internal `NO_APLICA` sentinel is not exposed.

## Outcome

- Closed W09.P45.S234. A natural-person profile declaring `capital_inmobiliario` can now be created non-interactively without `--activity` or `--iva-regime`; the stored profile has no invented `activities.description` and no invented `iva.regime`.
- `projection_for_taxpayer` and `load_active_taxpayer_profile` now project that profile as `IVARegime.NO_APLICA`, while an explicit `--iva-regime EXENTO` still projects and persists as `EXENTO`.
- Legal-entity, attribution-entity, and natural-person economic-activity paths still receive the wizard `GENERAL` default and remain covered by validation/readiness gates.
- Verification passed: focused S234 CLI integration, full taxpayer-type CLI integration file, user-profile projection/completeness tests, wizard setup/status tests, Modelo applicability tests, setup/taxpayer-model focused tests, IVA choice/exempt tests, and touched-file ruff.

## Notes

- First code-review pass found a high issue: runtime taxpayer projection still defaulted absent `iva.regime` to `GENERAL`. The follow-up patch introduced `IVARegime.NO_APLICA`, added projection/status regression coverage, and kept the sentinel internal to projection rather than an operator wizard choice.
- A second reviewer was spawned but did not return before commit pressure; it was closed to free the agent slot. Local review after the high-finding fix found no remaining S234 blocker.
