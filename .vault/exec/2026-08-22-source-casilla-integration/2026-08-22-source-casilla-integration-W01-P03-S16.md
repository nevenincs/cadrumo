---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:67f0c4dda40b607a56baf94cf4035af3ac78a4520ebb92f2cc95724923be1066'
step_id: 'S16'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---




# verify discovery detects a new repository, assembler, helper, and readiness declaration independently

## Scope

- `dev/source_connectivity/tests/test_discovery.py`

## Description

- Add isolated source-tree specimens for repository, CLI ingress, calculation helper, readiness, and row-assembler growth.
- Assert each detector expands from its own structural contract without another capability family being present.
- Preserve typed payload, policy, operation, source-kind, grouping, and observation evidence in the assertions.

## Outcome

Every capability detector now has a mutation-shaped regression proving that a new independently introduced surface becomes visible. The tests require no production allowlist and no mocks or monkeypatching.

## Notes

Ruff passed and all five sequential unit tests passed. Synthetic source files are parsed by the real discovery functions and never imported or executed.
