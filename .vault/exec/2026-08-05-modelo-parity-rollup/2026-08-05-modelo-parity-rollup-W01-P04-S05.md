---
tags:
  - '#exec'
  - '#modelo-parity-rollup'
date: '2026-08-04'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:3fdba8dba50354dc7544650af391ec14efa1f43a42594b184a2f2db3b6810938'
step_id: 'S05'
related:
  - "[[2026-08-05-modelo-parity-rollup-plan]]"
---

# Enforce reverse formula-target and casilla-kind parity in the registry validator

## Scope

- `src/cadrumo/domain/calculations/registry/_validate.py`

## Description

- Reused the lossless producer inventory in the registry validator.
- Rejected computed casillas without a formula producer.
- Rejected formula declarations on non-computed casillas.
- Preserved existing exact formula identity, duplicate-target, and dangling-direction checks through the existing validation path.
- Added real mutation tests for both directions and duplicate targets.

## Outcome

The accepted reverse-wiring contract is implemented without changing production formulas or model data. The worker reported 7 focused wiring tests and 263 broader registry tests passing, with targeted typing and formatting clean. The current replay reaches the unrelated profile-schema load failure first, so the six validator tests are not currently re-certified in shared state.

## Notes

The invariant is not tested through mocks or copied business logic. Full-project pytest and full-project typing remain outside the verified boundary.
