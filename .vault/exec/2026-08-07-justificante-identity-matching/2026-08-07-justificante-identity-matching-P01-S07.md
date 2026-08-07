---
tags:
  - '#exec'
  - '#justificante-identity-matching'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:e6edf736fbcdd5d360af7c02e302df7210773d513f2c8af0b48fb764d07e1507'
step_id: 'S07'
related:
  - "[[2026-08-07-justificante-identity-matching-plan]]"
---

# Run the domain and application justificante test suites and confirm green

## Scope

- `src/cadrumo/domain/justificante/tests and src/cadrumo/application/live/tests`

## Description

Gate run for the Phase, sequential per the local-execution rule, with full output
captured to a file and read back rather than piped through a truncating filter.

## Outcome

The plan's named command over the domain justificante tests and the application
live tests, in the unit lane with xdist disabled: **312 passed, 0 failed**, 2
deselected.

The 2 deselected tests were then run in their own lane and both fail on the
live-AEAT opt-in environment flag being unset - the safety gate refusing to run,
which is the mandated default and not a regression. They were not enabled.

## Verification

Wider gates were also run and every red was attributed to another owner before
this row was closed. The import-hygiene gate (3 failures) names four test files,
none of them touched here; the docstring core-struct-link gate (2 failures) names
seven modules, none touched here; the JSON schema conformance gate fails on a
`pull_all` versus `pull-all` CLI leaf mismatch from a concurrent campaign's new
verb. No file changed by this plan appears in any failure. None were patched.

## Notes

`ty check` is clean on the domain justificante package and on every file changed
here; the remaining diagnostics under `application/live` and `sede` are all in
peer-owned test files.
