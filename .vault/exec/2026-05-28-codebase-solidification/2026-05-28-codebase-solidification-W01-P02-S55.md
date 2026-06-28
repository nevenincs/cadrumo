---
step_id: S55
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P02.S55 — wire _sink.py warning through get_logger

## Outcome

Added `from ..logging import get_logger` import and `logger = get_logger(__name__)`
module-level constant to `src/aeat/core/observability/_sink.py`. Replaced the
inline `logging.getLogger(__name__).warning(...)` call at line 117 with
`logger.warning(...)`.

Circular-import safety confirmed before acting: `_context.py`, `_fingerprint.py`,
`_recorder.py`, and `_store.py` all already import `get_logger` at module top
without issues. The eager import is safe because `aeat.core.logging` only
imports from `observability` lazily inside `_install_run_context_record_factory`.

## Files touched

- `src/aeat/core/observability/_sink.py`

## Verification

`uv run --no-sync pytest src/aeat/core/observability/ -xvs` — 63 passed, 1 skipped.
Commit SHA: `534818caf`. `vault plan step check S55` applied.
