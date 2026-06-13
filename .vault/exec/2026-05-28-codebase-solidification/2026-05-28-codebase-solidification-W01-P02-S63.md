---
step_id: S63
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P02.S63 — attach_run_sink helper + SecretScrubbingFilter on JSONL sink

## Outcome

Added `attach_run_sink(sink)` to `src/aeat/core/logging.py`. The helper
installs `SecretScrubbingFilter` on `sink` if not already present, then
calls `logging.getLogger().addHandler(sink)`. This guarantees scrubbing
fires on every record flowing through the JSONL sink before it reaches the
serialiser.

`src/aeat/core/observability/_context.py` now imports `attach_run_sink`
from `..logging` and replaces `root_logger.addHandler(sink)` with
`attach_run_sink(sink)`. Also removed the pre-existing unused `Settings`
import from `_context.py`.

## Files touched

- `src/aeat/core/logging.py`
- `src/aeat/core/observability/_context.py`

## Verification

`uv run --no-sync pytest src/aeat/core/observability/ -x -q` — 85 passed, 1 skipped (pre-existing).
`vault plan step check S63` applied.
