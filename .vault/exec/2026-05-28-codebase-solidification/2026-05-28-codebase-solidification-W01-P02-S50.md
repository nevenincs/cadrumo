---
step_id: S50
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W01.P02.S50 — _stdio logger SecretScrubbingFilter test

## Outcome

Extended `src/aeat/entrypoints/cli/test_stdio.py` with two real-behavior tests:

- `test_stdio_logger_records_are_scrubbed_after_configure_logging`: calls real
  `configure_logging()`, emits a debug record with NIF `12345678Z` as a `%s`
  arg through `logging.getLogger("aeat.entrypoints.cli._stdio")`, and asserts
  the NIF literal does not appear in the formatted message. Confirms root-
  propagation scrubbing via `SecretScrubbingFilter`.

- `test_stdio_logger_scrubbing_filter_present_on_root_after_configure`: asserts
  `SecretScrubbingFilter` is installed on the root logger after
  `configure_logging()` — the structural precondition for the propagation path.

Added `import logging` to the top-of-file import block.

## Files touched

- `src/aeat/entrypoints/cli/test_stdio.py`

## Verification

`uv run --no-sync pytest src/aeat/entrypoints/cli/test_stdio.py -xvs` — 16 passed.
`vault plan step check S50` applied.
