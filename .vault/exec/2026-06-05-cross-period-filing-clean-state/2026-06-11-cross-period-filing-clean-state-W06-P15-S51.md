---
tags:
  - '#exec'
  - '#cross-period-filing-clean-state'
date: '2026-06-11'
step_id: 'S51'
related:
  - '[[2026-06-05-cross-period-filing-clean-state-plan]]'
---

# `cross-period-filing-clean-state` `W06.P15.S51` exec - evidence reference blockers

## Description

Cover live-capture evidence with matching justificante metadata as clean.
Cover live-capture evidence without persisted justificante metadata as `missing_external_evidence_record`.
Cover a stale justificante object whose period does not match the filing as `mismatched_external_evidence_record`.
Cover the repair diagnostic mapping for the mismatch blocker.

## Outcome

The real repository tests now prove reconciled, missing-object, CSV-only, live-capture-only, and stale-object evidence states produce explicit clean-state verdicts and repair guidance.

## Verification

Command passed: `uv run pytest src/aeat/application/calculations/tests/test_cross_period_clean_state.py src/aeat/application/modelo/tests/test_cross_period_clean_state_gates.py -q` with 30 tests passing.

Command passed: `uv run ruff check src/aeat/domain/deadlines/_models.py src/aeat/application/calculations/_cross_period_clean_state.py src/aeat/application/calculations/tests/test_cross_period_clean_state.py src/aeat/application/modelo/_verification_actions.py src/aeat/application/modelo/tests/test_cross_period_clean_state_gates.py`.

## Notes

The import-to-filing workflow binding steps `S50` and `S52` remain open; this step closes only the clean-state verifier and repository-level evidence blocker coverage.
