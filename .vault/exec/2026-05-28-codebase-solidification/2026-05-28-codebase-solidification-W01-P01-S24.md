---
step_id: S24
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P01.S24 — PensionReduccionError tests

## Outcome

Added `TestPensionReduccionErrorEnvelope` class to
`src/aeat/entrypoints/cli/test_modelo.py` with eight real-behavior tests
covering all six guard raises (three DT12, three SAL), subtype assertions
(CoreValidationError + ValueError), and registered error code
`REFUSED_PENSION_REDUCCION_COMPUTATION`. All tests exercise the real
production functions directly. Also fixed two pre-existing test regressions
in the same file: `ModeloRecordPayload` dict subscript migrated to attribute
access, and M303 period token assertion updated for expanded monthly registry
tokens.

## Files touched

- `src/aeat/entrypoints/cli/test_modelo.py` (TestPensionReduccionErrorEnvelope class; two pre-existing test fixes)

## Commit

`07378f2c0`
