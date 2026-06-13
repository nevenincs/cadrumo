---
step_id: S225
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-05-30'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
  - "[[2026-05-30-codebase-solidification-audit]]"
---

# codebase-solidification W02.P10.S225

## Outcome

Exposed `detach_run_sink(sink: logging.Handler) -> None` in `src/aeat/core/logging.py` as the symmetric counterpart to `attach_run_sink`. The helper removes the handler from the root logger, strips any `SecretScrubbingFilter` instances installed by `attach_run_sink`, and flushes the sink.

Updated `src/aeat/core/observability/_context.py` to import and call `detach_run_sink` instead of the raw `root_logger.removeHandler(sink)` at the unwind path. Removed the now-unused `root_logger = logging.getLogger()` local and the bare `import logging` statement.

## Files touched

- `src/aeat/core/logging.py` — added `detach_run_sink`
- `src/aeat/core/observability/_context.py` — routed detach through `detach_run_sink`; removed orphaned `import logging` and `root_logger` local

## Commit

f45c2c4e6
