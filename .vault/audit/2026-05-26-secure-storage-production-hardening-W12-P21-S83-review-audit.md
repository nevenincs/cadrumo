---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
modified: '2026-05-26'
related:
  - '[[2026-05-26-secure-storage-production-hardening-W12-P21-S83]]'
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---



# `secure-storage-production-hardening-W12-P21-S83` Code Review

S83-001 | HIGH | Reset-state test uses a synthetic emitter and production exposes the seam

`src/aeat/application/workflow/_persistence.py` adds an `emit_reset` constructor parameter and stores it as `_emit_reset`; the only discovered non-default caller is `src/aeat/application/workflow/test_persistence.py`, where `_raise` is injected to simulate downstream failure. This is a test double despite avoiding mock naming, violates the local no-fakes/no-stubs/no-monkeypatch testing rule, and leaves a public repository constructor path that can delete workflow state without the real `emit_workflow_state_reset` audit path. Rework the proof to drive a real event-persistence failure path or remove the injection seam so reset-state always uses the production event emitter.

Resolution: closed in S83 before plan-row closure. `WorkflowStateRepository` no longer accepts an emitter override, and the reset-state proof now corrupts the real bucket-event catalogue through the secure-object API so the production `workflow_state.reset` event path raises before deletion. The post-failure assertion verifies the workflow-state fingerprint remains readable.
