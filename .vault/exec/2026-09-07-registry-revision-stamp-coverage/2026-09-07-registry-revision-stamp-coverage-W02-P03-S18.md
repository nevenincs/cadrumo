---
tags:
  - '#exec'
  - '#registry-revision-stamp-coverage'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:2f5cb03ccf41523abcef0bc9ea83444a7c9083bc83d751a180797c8a34f22036'
step_id: 'S18'
related:
  - "[[2026-09-07-registry-revision-stamp-coverage-plan]]"
---

# Require the producing RegistrySnapshotRef on VerificationReport and validate it against its parent CalculationRevision

## Scope

- `src/cadrumo/domain/modelos/verification_report.py`
- `src/cadrumo/adapters/persistence/profile/modelos_verification_reports.py`

## Changes

- `M` `src/cadrumo/domain/modelos/verification_report.py`
- `M` `src/cadrumo/adapters/persistence/profile/modelos_verification_reports.py`
