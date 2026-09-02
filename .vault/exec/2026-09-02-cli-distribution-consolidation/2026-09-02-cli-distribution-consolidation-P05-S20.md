---
tags:
  - '#exec'
  - '#cli-distribution-consolidation'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:6063ace8121a6c06684fc432de54ec3c206cceaf9d60282afbbe694e944ed128'
step_id: 'S20'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---
# Retire the second console script, repoint its entry-point test, and assert the headless full-screen start in the distribution smoke check

## Scope

- `src/cadrumo/entrypoints/tui/tests/test_installed_entrypoint.py`

## Changes

M src/cadrumo/entrypoints/tui/tests/test_installed_entrypoint.py

## Notes

The smoke-check assertion this Step's action names is not added: the distribution smoke
check probes an installed artifact, and the full-screen session cannot currently reach a
clean exit because of a defect in the operation registry's composition. Adding an
assertion known to fail would make the smoke check dishonest.
