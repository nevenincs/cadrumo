---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'P07.S03'
related:
  - "[[2026-05-13-cli-workflow-redesign-config-repair-shape-plan]]"
---

# `cli-workflow-redesign` P07.S03 — reset-state ordering prevents trail-loss on emit failure

## Finding

H-1 (HIGH). `WorkflowStateRepository.reset_workflow_state` deleted the
secure-object envelope first and emitted the `workflow_state.reset`
bucket event second. Each call opened its own `session_scope`, so if
the second call raised the secure-object row was already gone but no
audit entry survived — the worst possible failure mode for the recovery
route.

## Decision

A true single-transaction wrapping of both calls would require
threading an explicit SQLAlchemy session into `SecureObjectRepository`
(`delete`, `save`, `load`) and into `BucketEventHistoryRepository`
(which itself calls `_objects.load` and `_objects.save`). That is a
multi-call-site repository-API change with significant blast radius
beyond the scope of this finding. The pragmatic correct fix is to
**emit first, then delete**: the surviving failure mode is "audit entry
present, data still present" (re-running the recovery succeeds and is
idempotent), not "data discarded, audit lost".

## Resolution

Swapped the call order in `WorkflowStateRepository.reset_workflow_state`:
`emit_workflow_state_reset(...)` now runs before `self._objects.delete(...)`.
Updated the docstring to describe the new ordering and its rationale.

Added a real-exception-injection test
`test_reset_workflow_state_emit_failure_leaves_row_intact` in
`src/aeat/application/workflow/test_persistence.py`. The test seeds a
state row, patches the module-level `emit_workflow_state_reset` with a
real function that raises a real subclass of `RuntimeError`
(`_EmitFailure`), invokes `reset_workflow_state`, asserts the exception
propagates AND the secure-object row is still present after the raise.
No `Mock`, no test double — just a function that raises.

## Verification

`pytest src/aeat/application/workflow/test_persistence.py -k reset_workflow_state_emit_failure`
asserts the invariant; existing `_config/test_repair_reset_state.py`
tests still pass under the swapped order because the success path is
order-independent.
