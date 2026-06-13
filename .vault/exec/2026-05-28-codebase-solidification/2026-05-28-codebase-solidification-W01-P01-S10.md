---
step_id: S10
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P01.S10 — WorkflowInputMismatchError tests

## Outcome

Added `TestWorkflowInputMismatchError` class to
`src/aeat/application/modelo/test_actions.py` with five real-behavior tests:
matching request does not raise, mismatched modelo raises with context,
mismatched period raises with context, subtype assertions
(CoreValidationError + ValueError), and registered error code
`REFUSED_WORKFLOW_INPUT_MISMATCH`. All tests exercise the real
`_RevisionInputsProvider.load_inputs` production path.

## Files touched

- `src/aeat/application/modelo/test_actions.py` (TestWorkflowInputMismatchError class, import of _RevisionInputsProvider and WorkflowInputMismatchError)

## Commit

`07378f2c0`
