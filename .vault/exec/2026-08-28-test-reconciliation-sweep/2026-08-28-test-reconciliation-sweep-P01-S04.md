---
tags:
  - '#exec'
  - '#test-reconciliation-sweep'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:1fa8730ab52ffd7979faf3e0a0d48073e82079a6714669a021d82e1e5ca6082d'
step_id: 'S04'
related:
  - "[[2026-08-28-test-reconciliation-sweep-plan]]"
---

# Grant the source-mesh purchase its INVOICE_EVIDENCE deduction authority so the input leg is asserted against real values

## Scope

- `src/cadrumo/entrypoints/cli/tests/`

## Changes

- `M` `src/cadrumo/entrypoints/cli/tests/test_modelo_source_mesh_calculate.py`
- `verify:` `pytest src/cadrumo/entrypoints/cli/tests/test_modelo_source_mesh_calculate.py -m integration` -> `pass`
