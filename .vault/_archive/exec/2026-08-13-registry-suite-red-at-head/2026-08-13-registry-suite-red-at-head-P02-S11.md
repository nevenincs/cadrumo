---
tags:
  - '#exec'
  - '#registry-suite-red-at-head'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:16c76be7380a6278b4899aebc3710f3c67924b429b1cf2014882b16c5b1fbc1e'
step_id: 'S11'
related:
  - "[[2026-08-13-registry-suite-red-at-head-plan]]"
---
# `P02.S11` - Re-run the M322, M353 and M390 manual worked examples and confirm each reproduces its AEAT figure, treating a swept fixture whose oracle has not executed as not done

Scope: `src/cadrumo/domain/calculations/registry/tests/`.

## Description

- Run the M322, M353 and M390 AEAT manual worked examples sequentially after P02.S05.
- Confirm each test reaches its numeric assertions with the original expected figures.
- Record the exact post-review rerun rather than inferring success from a mixed lane.

## Outcome

The exact sequential route over the three manual modules passed eleven tests in 29.24 seconds after the S05 review repair. M322 and M353 contributed five passing tests; M390 contributed six. The deduction changes only supplied legal classification provenance and did not modify any AEAT expected value.

## Notes

The route used `-n0` as required by the accepted ADR. No alternative Git index was used. No oracle expectation, skip, xfail, mock, patch, fake, or compatibility path was introduced.
