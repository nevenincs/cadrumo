---
tags:
  - '#exec'
  - '#test-reconciliation-sweep'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:ab9d604fa4a3c2462bd279dd5de29bf0d9ed57924ae87671404839c53d8b63c2'
step_id: 'S06'
related:
  - "[[2026-08-28-test-reconciliation-sweep-plan]]"
---

# Declare the Modelo 111 colegio-concertado attestation in the test profile, since readiness and the export producer both genuinely require it

## Scope

- `src/cadrumo/entrypoints/cli/tests/`

## Changes

- `M` `src/cadrumo/entrypoints/cli/tests/test_modelo_source_mesh_calculate.py`
- `verify:` `pytest src/cadrumo/entrypoints/cli/tests/test_modelo_source_mesh_calculate.py -m integration` -> `pass`
