---
tags:
  - '#exec'
  - '#registry-revision-stamp-coverage'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:6fba9c6396eb6d16d341ebb5f7d4fa3a5a25c8a1a8d0125253be93dd30d7b16c'
step_id: 'S19'
related:
  - "[[2026-09-07-registry-revision-stamp-coverage-plan]]"
---

# Copy and validate the CalculationRevision coordinate when verification reports are created and loaded

## Scope

- `src/cadrumo/application/modelo/verification_actions.py`
- `src/cadrumo/adapters/persistence/profile/modelos_verification_reports.py`

## Changes

- `A` `src/cadrumo/application/calculations/verification_report_gate.py`
- `M` `src/cadrumo/application/modelo/verification_actions.py`
- `M` `src/cadrumo/adapters/persistence/profile/modelos_verification_reports.py`
