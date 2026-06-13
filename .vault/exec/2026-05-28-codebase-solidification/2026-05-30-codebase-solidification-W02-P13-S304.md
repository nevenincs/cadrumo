---
step_id: S304
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-05-30'
agent: coder-iota6
commit: ae373e0f4
status: closed
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W02.P13.S304

Annotated intentional `os.environ` write sites in `src/aeat/core/observability/_replay.py`:
- Line 172: `os.environ[REPLAY_ACTIVE_ENV_VAR] = run_id  # env-write: intentional — scoped context-manager`
- Line 179: `os.environ[REPLAY_ACTIVE_ENV_VAR] = previous  # env-write: intentional — restore prior state`

These writes are inside a scoped context-manager that always restores the previous value in the `finally` block. The comments document the intentional escape from the Settings-not-naked-env rule.
