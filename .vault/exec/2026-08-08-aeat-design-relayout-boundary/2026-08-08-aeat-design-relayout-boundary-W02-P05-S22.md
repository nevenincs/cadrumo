---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-08-18'
modified: '2026-08-18'
body_schema: 'body-v1'
body_hash: 'sha256:e3855928fe598a9e1662d61979ae43c7741e2c2dd95b805713c8584d22ab0e21'
step_id: 'S22'
related:
  - "[[2026-08-08-aeat-design-relayout-boundary-plan]]"
---

# `aeat-design-relayout-boundary` execution record: `W02.P05.S22`

Author the Modelo 303 revision covering the earliest in-window filing year with valid_from at that year and no earlier sibling.

## Executed

- The prescripcion-reachable window computed in `W01.P01.S02` names filing year 2022 onward, so the bounded historical revision now covers exactly 2022: directory renamed `2009-2022` -> `2022`, every fragment key re-keyed, `valid_from = 2022-01-01`, `period_selector = { year_from = 2022, year_to = 2022, periods = [1T..4T] }`.
- Every consumer swept in the same atomic landing: 376 registry fragments in the renamed tree, the cross-modelo dependency references in other modelos' registries, 146 test files, the m303 orden constants and the IVA-wallet relation targets, and the three dev harness files.

## Verification

- `load_modelo_directory` on modelo 303 loads clean with revisions `2022, 2023, 2024-desde-09-y-3t, 2024-hasta-08-y-2t, 2025, 2026-y-siguientes`.
- Full-tree `pytest --collect-only` collects 25030 tests; the only three collection errors are the peer's in-flight `cadrumo.tests._inventory` rename, not this step's.
- The span gate adds no `modelo 303 revision '2022'` failure.
- Whole-registry validation failures show no 303-2022 line beyond the known export-layout and deadline-window gaps this plan tracks separately.
