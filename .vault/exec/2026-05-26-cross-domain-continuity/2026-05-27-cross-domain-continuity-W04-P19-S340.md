---
tags:
  - "#exec"
  - "#cross-domain-continuity"
date: "2026-05-27"
modified: '2026-05-27'
step_id: S340
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---


# cross-domain-continuity W04.P19.S340 — workflow abort surface: DRAFT_HAS_ERRORS next_action pointer

## Summary

S340 (SMALL) surfaced by Andrea round-9: when `DRAFT_HAS_ERRORS` aborts the workflow, the abort step emits only `status_value` / `error_count`. Operators see no pointer to `verification-report list` and cannot find their persisted findings without knowing the command.

## Changes

Two touch-points:

- `_stage_validating_draft` in `src/aeat/application/workflow/_engine.py`: the `WorkflowStep.details` dict for the DRAFT_HAS_ERRORS abort path now carries a `next_action` key alongside `error_count`. The key contains the retrieval command template (`aeat app modelo work verification-report list <calculation_revision_id>`).

- `_verification_report_lines` in `src/aeat/entrypoints/cli/_modelo.py`: when `not report.granted_verificado_completo`, a `next_action` tab-delimited line is appended pointing to `aeat app modelo work verification-report list <calculation_revision_id>` with the real calculation_revision_id interpolated.

No new `tr()` keys — the pointer text is inline. Locale audit confirms zero drift.

## Tests

- `TestAbortReasons::test_draft_has_errors_surfaces_next_action_pointer` in `src/aeat/application/workflow/test_engine.py`: engine unit test asserting `details["next_action"]` is present and contains `"verification-report list"` on DRAFT_HAS_ERRORS abort.
- `test_verification_report_lines_includes_next_action_when_refused` in `src/aeat/entrypoints/cli/test_modelo.py`: CLI unit test asserting the `next_action\t` line is present with the calculation_revision_id when `granted=False`.
- `test_verification_report_lines_omits_next_action_when_granted` in `src/aeat/entrypoints/cli/test_modelo.py`: anti-tautology — granted reports must NOT emit `next_action`.

All 3 pass; the 18-test `TestAbortReasons` class passes without regression.
