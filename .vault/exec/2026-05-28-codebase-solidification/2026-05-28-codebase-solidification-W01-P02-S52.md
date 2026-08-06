---
step_id: S52
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-07-17'
body_hash: 'sha256:7ec5c115e4f220f7fdbe541225200eb320f4f315ce59e73c91b04dd17710e4f3'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P02.S52 — overview logger SecretScrubbingFilter test

## Outcome

Created `src/aeat/entrypoints/cli/test_overview.py` with three real-behavior
tests that exercise the module-level `logger` in `_overview.py`:

- `test_overview_logger_has_secret_scrubbing_filter` — asserts filter presence
  on the logger or root logger chain.
- `test_overview_logger_scrubs_nif_in_log_record` — emits a WARNING record
  carrying a NIF via `logger.warning("... tax_id=%s", nif)`, captures via
  `caplog`, asserts NIF absent and `<redacted>` present in `getMessage()`.
- `test_overview_logger_scrubs_nif_in_message_body` — same pattern with a
  different NIF to cover arg-position scrubbing.

No mocks, no skips, no tautologies. Scrubbing verified against real filter
mutation on `record.args`.

## Files touched

- `src/aeat/entrypoints/cli/test_overview.py` (created)

## Verification

`uv run --no-sync pytest src/aeat/entrypoints/cli/test_overview.py -xvs` — 3 passed.
`vault plan step check S52` applied.
