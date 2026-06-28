---
step_id: S261
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-05-30'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
  - "[[2026-05-30-codebase-solidification-audit]]"
---

# codebase-solidification W02.P11.S261

**Raise site:** `src/aeat/application/workflow/_engine.py:282`

**Change:** Replaced `raise ValueError("resumed_from must be a 16-character lowercase hex run id...")` with `raise WorkflowInputMismatchError(...)`. `WorkflowInputMismatchError` was moved to `workflow/_errors.py` by a prior commit (S09/S266 wave); imported via `._errors` in `_engine.py` and exported from `workflow/__init__`.

**Architecture note:** Keeping the class in `workflow/_errors.py` avoids a circular import (`modelo._actions` already imports from `..workflow`).

**Tests:** `test_engine.py` updated assertion from `ValueError` to `WorkflowInputMismatchError`; 46 engine tests + 13 resume tests pass (59 total). `test_actions.py` `TestWorkflowInputMismatchError` (5 tests) pass via re-export in `_actions.py`.

**Commit:** `d76cbf66e`
