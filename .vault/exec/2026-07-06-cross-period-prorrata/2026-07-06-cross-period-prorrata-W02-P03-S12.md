---
tags:
  - '#exec'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:6f3e50cecc8e5e98322dff9defe85f9849efa2c3a420c27b5cf00788a905e3a7'
step_id: 'S12'
related:
  - "[[2026-07-06-cross-period-prorrata-plan]]"
---

# record the source observation identity on the seeded entry so the register stays cross-checkable against the prior filing forever after

## Scope

- `src/aeat/application/prorrata_register/_seed.py`

## Description

- Record the prior Modelo 303 observation identity on every seeded carried entry via `source_observation_ref`.
- Use the existing register convention `303:<source-year>:<source-period>` so the entry can be cross-checked against the prior filing later.
- Keep the S10/S11 seed and finding behavior unchanged.

## Outcome

- A clean 2025 Modelo 303 4T prior observation now seeds the 2026 carried entry with `source_observation_ref` equal to `303:2025:4T`.
- Scoped gates passed: `ruff check src/aeat/application/prorrata_register/_seed.py`, direct import smoke, real encrypted-repository smoke for the source identity, and `pytest -q src/aeat/domain/prorrata_register/tests/test_prorrata_register.py src/aeat/adapters/persistence/profile/tests/test_prorrata_register_roundtrip.py src/aeat/application/modelo/tests/test_prorrata_regularizacion_advisory.py` (`27 passed`).

## Notes

- The broader committed seed tests remain the dedicated `W02.P03.S13` row.
