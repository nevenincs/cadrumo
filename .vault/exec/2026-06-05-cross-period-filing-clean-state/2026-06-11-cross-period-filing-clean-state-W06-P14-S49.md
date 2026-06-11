---
tags:
  - '#exec'
  - '#cross-period-filing-clean-state'
date: '2026-06-11'
step_id: 'S49'
related:
  - '[[2026-06-05-cross-period-filing-clean-state-plan]]'
---

# `cross-period-filing-clean-state` `W06.P14.S49` exec - evidence reference resolution

## Description

Add clean-state resolution of justificante-backed external evidence records.
Require AEAT justificante/live-capture references to resolve through the justificante repository.
Reject resolved justificante records whose modelo, ejercicio, or period do not match the filing record.
Surface a typed `mismatched_external_evidence_record` blocker for stale or cross-bound receipt references.
Map the mismatch blocker to the operator reconcile/import repair path.

## Outcome

Cross-period clean-state evaluation no longer treats a matching reference id alone as proof that an upstream filing was submitted to AEAT. A filing backed by justificante or live-capture evidence must now resolve to a persisted justificante artifact matching the same modelo, filing year, and period.

## Verification

Command passed: `uv run pytest src/aeat/application/calculations/tests/test_cross_period_clean_state.py src/aeat/application/modelo/tests/test_cross_period_clean_state_gates.py -q` with 30 tests passing.

Command passed: `uv run ruff check src/aeat/domain/deadlines/_models.py src/aeat/application/calculations/_cross_period_clean_state.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py src/aeat/application/modelo/_verification_actions.py src/aeat/application/modelo/tests/test_cross_period_clean_state_gates.py`.

## Notes

`uv run pytest` initially exposed a deadlines import drift where `Annotated` was imported from pydantic instead of typing. The import was corrected so the calendar/modelo import path can load under the locked pydantic v2 environment.
