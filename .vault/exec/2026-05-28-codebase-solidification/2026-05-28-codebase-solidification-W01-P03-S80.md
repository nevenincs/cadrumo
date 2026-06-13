---
step_id: S80
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P03.S80 — no_active_profile output test

## Outcome

Extended `src/aeat/entrypoints/cli/test_common.py` with three real-behavior
tests covering S79:

- `test_active_profile_or_exit_locale_keys_resolve_to_real_strings`: asserts
  that both new locale keys resolve to non-placeholder, non-empty strings in
  the en catalogue without any CLI invocation.
- `test_active_profile_or_exit_emits_localized_payload_in_text_channel`:
  invokes `aeat app ledger list` (cold-start, no profile) via `invoke_cached_cli`
  against an `isolated_sessionless_storage_root`; asserts exit code is non-zero
  and the locale-resolved next-step value appears in output.
- `test_active_profile_or_exit_emits_localized_payload_in_json_channel`:
  same invocation with `--format json` at root level; asserts locale-resolved
  error or next value appears in output.

All tests use real CLI runner and real storage isolation; no mocks.

## Files touched

- `src/aeat/entrypoints/cli/test_common.py`

## Verification

`pytest src/aeat/entrypoints/cli/test_common.py -xvs` — 6 passed.
`python -m aeat.locales audit` — en/es/ca/hu all ok.
`vault plan step check S80` applied.
