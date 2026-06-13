---
step_id: S75
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W01.P02.S75 — SecretScrubbingFilter on attach_run_sink path

## Outcome

Verified and re-confirmed: `attach_run_sink()` in `src/aeat/core/logging.py`
(lines 356-372, landed in commit 3086071865) already installs `SecretScrubbingFilter`
on the sink before calling `logging.getLogger().addHandler(sink)`. This is the
canonical path used by `run_context` in `src/aeat/core/observability/_context.py`
(line 246). No code change was required. The pattern is:
  1. `attach_run_sink(sink)` installs filter + attaches to root.
  2. `configure_logging()` additionally installs filter on root logger and every handler.
Both layers are idempotent (guard checks for existing `SecretScrubbingFilter` instance).

## Files touched

None (verification pass only).

## Verification

Confirmed in `src/aeat/core/logging.py:370-372`; confirmed in `_context.py:246`.
S76 test exercises the full path end-to-end.
