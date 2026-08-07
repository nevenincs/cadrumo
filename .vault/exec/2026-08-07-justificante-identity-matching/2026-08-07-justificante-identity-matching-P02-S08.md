---
tags:
  - '#exec'
  - '#justificante-identity-matching'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:650d4c2513631633376156c266a7bdd0d69d7e0ffb9d1e4366989e362d8272fb'
step_id: 'S08'
related:
  - "[[2026-08-07-justificante-identity-matching-plan]]"
---

# Distinguish all five swallowed outcomes (unreadable artefact, manifest mismatch, unparsable PDF, CSV-resolution failure, CSV mismatch) and return a typed reason instead of returning None uniformly

## Scope

- `src/cadrumo/application/live/_filed_observation_persistence.py (_parse_matching_filed_justificante)`

## Description

Five distinct dead ends shared one shape - a warning log plus a bare `None` - so a
run extracting casillas while enrolling nothing reported an unexplained zero,
indistinguishable from a period with no receipt.

## Outcome

Added `FiledJustificanteUnreachedReason`, a `StrEnum` beside its carrier, and a
frozen record holding either a receipt or the reason there is none. Every branch
of `_parse_matching_filed_justificante` now returns its own member.

The enum carries SIX members, not the five the ADR enumerates: the ADR's list
omits the pre-existing filing-target rejection branch, which the reference does
count. Folding it into another member would have re-created the collapse this row
exists to undo, so `FILING_TARGET_MISMATCH` is named explicitly.

## Verification

Covered by `test_each_unreached_justificante_outcome_reports_its_own_reason`, which
compares the SET of reasons rather than their count, so a branch collapsing any
two back together still fails.

## Notes

The enum lives in the application module rather than `core/`, following the
nearest analogues - `ObservedCasillaSkip.reason` beside its carrier in the sede
adapter, and `ReviewItemKind` in the review package's own enum module - rather
than promoting an application-local diagnostic vocabulary into the shared core
spine.
