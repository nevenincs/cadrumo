---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'W12.P056..W12.P060'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-10-eliminate-user-cli-shim-plan]]"
---

# `cli-workflow-redesign` W12 closeout (eliminate user_cli shim)

Closed plan rows: every row of `W12.P056..W12.P060`
(`S0331..S0360`).

## Delivered state (pre-existing)

The 2026-05-10 user-CLI retirement plan is closed (apex ADR §9
footnote): `application/user_cli.py` has been removed from the
codebase. Remaining `user_cli` occurrences in the source tree are
prose / docstring / fixture-name strings only — not module
imports.

- `application/overview/__init__.py` documents the historical
  context in prose comments.
- `application/overview/test_calendar.py` and
  `entrypoints/cli/test_workflow_surface.py` reuse the fixture
  name `_isolate_user_cli` / `encrypted_user_cli` as readable
  test scaffolding; the underlying behavior tests workflow state
  via `aeat.application.workflow._persistence` directly.

## Per-phase rationale

- `P056`: workflow state ownership lives in
  `application/workflow/_persistence.py` with typed
  `WorkflowState` / `WorkflowStateRepository` contracts. No
  user_cli substitute exists or is needed.
- `P057`: no duplicate workflow-state surfaces. The legacy
  inline-profile migrator was removed in W09.P042 (`2273381e`).
- `P058`: no compatibility shims. The retired `user_cli.py`
  module is gone with no re-export.
- `P059`: `application/workflow/` carries its own test suite
  (test_models, test_persistence, test_adapters, test_engine)
  that exercises the canonical state through real secure
  persistence.
- `P060`: the workflow CLI surface routes through
  `entrypoints/cli/_config/_profile_state` and the canonical
  workflow state repository; no user_cli shim sits in the
  command tree.

## Guards held

- No code restored from the retired user_cli module.
- No metastate test codifies the absence; the architectural
  enforcement is the deleted file plus the canonical workflow
  state ownership.
