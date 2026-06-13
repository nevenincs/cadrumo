---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-30'
modified: '2026-05-30'
step_id: 'S242'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# `codebase-solidification` `W02.P10.S242`

Added real-behavior test `TestReplayActiveEnvVarCanonicity` to `test_replay.py` asserting `REPLAY_ACTIVE_ENV_VAR` has exactly one canonical definition site in the package.

- Modified: `src/aeat/core/observability/test_replay.py`

## Description

The test greps all non-test `.py` files under the `aeat.core.observability` package for the literal string `"AEAT_REPLAY_ACTIVE"`. It asserts exactly one hit exists, that it is in `_replay.py`, and that it is at line 26. The search token is assembled via string concatenation to prevent self-match within the test file itself. No mocks, no skips, no tautology.

## Tests

`uv run --no-sync pytest src/aeat/core/observability/ -x -q` — 68 passed, 1 skipped (pre-existing).
