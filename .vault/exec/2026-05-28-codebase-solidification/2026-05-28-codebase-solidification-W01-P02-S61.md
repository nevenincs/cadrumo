---
step_id: S61
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P02.S61 — set_log_level helper in aeat.core.logging

## Outcome

Added `set_log_level(level, *, file_level=logging.DEBUG)` to
`src/aeat/core/logging.py`. The helper calls `configure_logging()` first,
sets the root logger to `DEBUG`, then walks `root_logger.handlers` applying
`file_level` to `FileHandler` instances and `level` to all others.

`apply_to_root_logger` in `src/aeat/entrypoints/cli/_log_levels.py` now
delegates to `set_log_level(_STDERR_LOG_LEVEL_BY_CLI_LEVEL[level])` —
removing the inline traversal and the now-unused `from ...core import logging
as aeat_logging` import.

## Files touched

- `src/aeat/core/logging.py`
- `src/aeat/entrypoints/cli/_log_levels.py`

## Verification

`uv run --no-sync pytest src/aeat/core/test_logging.py src/aeat/entrypoints/cli/test_log_levels.py -x -q` — all passed.
`vault plan step check S61` applied.
