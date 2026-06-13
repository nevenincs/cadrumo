---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-30'
modified: '2026-05-30'
step_id: 'S241'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# `codebase-solidification` `W02.P10.S241`

Removed private duplicate `_REPLAY_ACTIVE_ENV_VAR = "AEAT_REPLAY_ACTIVE"` from `_context.py` and replaced with `from ._replay import REPLAY_ACTIVE_ENV_VAR`.

- Modified: `src/aeat/core/observability/_context.py`

## Description

The private literal at line 51 duplicated the canonical `REPLAY_ACTIVE_ENV_VAR` defined in `_replay.py:26`. The comment claimed a circular-import risk, but `_replay.py` has no import of `_context.py`, so the concern was unfounded. The private constant was also never referenced in the `_context.py` body — it was defined but unused. The fix imports the canonical name directly from `._replay` and removes the stale comment block.

## Tests

`uv run --no-sync pytest src/aeat/core/observability/ -x -q` — 68 passed, 1 skipped (pre-existing).
