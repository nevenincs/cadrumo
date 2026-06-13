---
step_id: S226
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-30
modified: '2026-05-30'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
  - "[[2026-05-30-codebase-solidification-audit]]"
---

# codebase-solidification W02.P10.S226

## Outcome

Extended `src/aeat/core/test_logging.py` with three real-behavior tests that wire a real `JsonlRunSink` through the full attach/detach cycle:

- `test_attach_and_detach_run_sink_are_symmetric` — asserts the root-logger handler list and sink filter list are restored to their pre-attach state after `detach_run_sink`; confirms `SecretScrubbingFilter` is installed on attach and removed on detach.
- `test_detach_run_sink_is_idempotent_on_filter_removal` — a second `detach_run_sink` call on an already-detached sink must not raise and must leave the filter list clean.
- `test_attach_run_sink_does_not_double_install_scrubbing_filter` — two consecutive `attach_run_sink` calls install `SecretScrubbingFilter` exactly once.

## Test result

`uv run --no-sync pytest src/aeat/core/test_logging.py src/aeat/core/observability/ -x -q` — 91 passed, 1 skipped (pre-existing skip in sink suite).

## Files touched

- `src/aeat/core/test_logging.py` — three new symmetry tests

## Commit

f45c2c4e6
