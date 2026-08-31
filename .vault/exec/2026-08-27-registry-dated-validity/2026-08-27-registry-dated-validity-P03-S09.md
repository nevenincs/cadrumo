---
tags:
  - '#exec'
  - '#registry-dated-validity'
date: '2026-08-27'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:d8dc3b3688690ecfd56166471ac53301622327bd60f3ca2ef37d9d930cdf6886'
step_id: 'S09'
related:
  - "[[2026-08-27-registry-dated-validity-plan]]"
---

# Prove every new gate bites by mutating the production data from outside the tracked tree, confirming each red and restoring, covering the omitted bound, the widened year-named citation and the widened provision window

## Scope

- `src/cadrumo/domain/ and src/cadrumo/core/`

## Changes

- `verify:` `out-of-tree mutation of all three shipped corpora` -> `pass`

## Notes

The first run of the bite proofs reported four passes for the wrong reason: the
harness never created its temp subdirectories, so every corpus refused with
`FileNotFoundError` and the harness counted the refusal as a gate biting. The
harness now treats an OS error as a broken proof rather than a red gate. A second
defect surfaced after that fix: the provision-window mutation widened only the
first citation, whose article has been in force since 1993, so nothing violated
and the proof passed while proving nothing. Both were corrected before the
recorded pass.
