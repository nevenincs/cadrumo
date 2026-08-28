---
tags:
  - '#exec'
  - '#test-reconciliation-sweep'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:db7da517ed5ec2ed3e0145bf316540ffe1c47935e7db1ce450c8e3686389de0f'
step_id: 'S05'
related:
  - "[[2026-08-28-test-reconciliation-sweep-plan]]"
---

# Repoint the M115 refusal assertion at the typed action projection that replaced the removed free-text field

## Scope

- `src/cadrumo/entrypoints/cli/tests/`

## Changes

- `M` `src/cadrumo/entrypoints/cli/tests/test_modelo_source_mesh_calculate.py`
- `verify:` `pytest src/cadrumo/entrypoints/cli/tests/test_modelo_source_mesh_calculate.py -m integration` -> `pass`
