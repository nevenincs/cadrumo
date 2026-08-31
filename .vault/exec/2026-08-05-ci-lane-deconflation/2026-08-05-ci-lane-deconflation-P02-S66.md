---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:5a6ee4b7495c7ac73234e4b0b5e5105068a7c112fee585641b31f47d2045c7f2'
step_id: 'S66'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---

## Changes

- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P02-S66.md`
- `verify:` `& .venv\Scripts\python.exe -m pytest -n 0 -q src/cadrumo/domain/calculations/registry/tests/test_export_layout_join_ratchet.py src/cadrumo/domain/calculations/registry/tests/test_modelo_349_registry.py::test_committed_modelo_349_record_design_round_trips_declarante_operador_rectificacion` -> `pass`

## Notes

- Fresh verification at current HEAD: `5 passed in 224.01s (0:03:44)`. Immutable implementation provenance is `ce7ed9c74ef76a656170e5c8060e4b68fa510779`; it contains no captured historical literal test output, so this fresh result is not presented as historical output.
