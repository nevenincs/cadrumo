---
tags:
  - '#exec'
  - '#registry-revision-stamp-coverage'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:4897afebe95d9eb5cd0b2558db51f82759520f08786c591f06c2fa7f273712f7'
step_id: 'S17'
related:
  - "[[2026-09-07-registry-revision-stamp-coverage-plan]]"
---

# Update CalculationRevision builders and round-trip tests to provide canonical coordinates and reject absent stamps

## Scope

- `src/cadrumo/domain/modelos/tests`
- `src/cadrumo/adapters/persistence/profile/tests/test_calculation_repository_roundtrip.py`

## Changes

- `M` `src/cadrumo/domain/modelos/tests/test_calculation_revision_evidence.py`
- `M` `src/cadrumo/domain/modelos/tests/test_calculation_revision_observations.py`
- `M` `src/cadrumo/domain/modelos/tests/test_calculation_revision_replay.py`
- `M` `src/cadrumo/adapters/persistence/profile/tests/test_calculation_repository_roundtrip.py`
