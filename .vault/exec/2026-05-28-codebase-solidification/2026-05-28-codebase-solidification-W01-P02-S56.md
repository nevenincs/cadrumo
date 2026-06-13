---
step_id: S56
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P02.S56 — test sink-failure warning passes through SecretScrubbingFilter

## Outcome

Added `class TestSinkEmitFailureWarningIsScrubbed` to
`src/aeat/core/observability/test_sink.py` with two real-behavior tests:

- `test_emit_failure_warning_scrubs_sensitive_exc_text` (POSIX only, skipped on
  Windows): uses `chmod(S_IREAD)` to make the target file unwritable, forces a
  `PermissionError` on write, captures the `WARNING` via `caplog`, and asserts
  the `aeat.core.observability._sink` logger carries `SecretScrubbingFilter`.

- `test_emit_failure_on_read_only_target_directory` (cross-platform): makes the
  target path itself a directory so `open("a")` raises `IsADirectoryError` /
  `PermissionError` on all platforms, captures the `WARNING`, and asserts
  the record name is `aeat.core.observability._sink` and the message is
  `"jsonl run sink emit failed"`.

Both tests are real-behavior — no mocks, no skips (except the chmod one on
Windows where chmod is not reliable for non-admin processes), no tautologies.

## Files touched

- `src/aeat/core/observability/test_sink.py`

## Verification

`uv run --no-sync pytest src/aeat/core/observability/test_sink.py -xvs` —
15 passed, 1 skipped.
`uv run --no-sync pytest src/aeat/core/observability/ -xvs` — 63 passed, 1 skipped.
Commit SHA: `534818caf`. `vault plan step check S56` applied.
