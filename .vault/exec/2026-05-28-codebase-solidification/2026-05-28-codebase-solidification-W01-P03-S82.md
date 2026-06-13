---
step_id: S82
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P03.S82 — ledger id-prefix fallthrough locale test

## Outcome

Created `src/aeat/entrypoints/cli/test_ledger.py` with two real-behavior tests:

- `test_id_prefix_unknown_key_renders_per_locale` — parametrized over all four
  supported locales, asserts the sentinel message is embedded in the rendered
  output and the key does not fall through as its own value.
- `test_id_prefix_unknown_key_distinguishes_locales` — asserts that at least
  two locales produce different prefix text before the sentinel, preventing
  silent copy-paste regressions.

No mocks, no patches, no skips. The tests exercise the real `tr()` pipeline
against the actual locale catalogues.

## Files touched

- `src/aeat/entrypoints/cli/test_ledger.py` (created)

## Verification

5 tests in `test_ledger.py` pass. Step closed via `vault plan step check`.
