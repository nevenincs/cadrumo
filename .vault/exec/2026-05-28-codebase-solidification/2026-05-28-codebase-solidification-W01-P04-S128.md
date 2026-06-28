---
step_id: S128
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P04.S128 — LLM cache malformed payload rejection tests

## Outcome

Extended `src/aeat/adapters/outbound/llm/test_cache.py` with two real-behavior tests:

- `test_entry_from_payload_rejects_malformed_bytes` (parametrised over 5 corrupted
  payload variants: bad JSON, empty bytes, invalid syntax, non-dict entry, incomplete
  response). Asserts `_entry_from_payload` raises rather than silently returning a
  partial `CachedEntry`.
- `test_entry_from_payload_rejects_wrong_logical_root` — constructs a syntactically
  valid payload with a foreign `logical_root` and asserts `LLMCacheError` with
  "different logical partition" message.

Also fixed a pre-existing `test_cache_payload_canary_is_encrypted_in_database` failure
where the test assumed `aeat.db` at `tmp_path` root but the bucket layout places it
under `aeat-storage/buckets/…/db/aeat.db`. Fixed to `rglob("*.db")`.

## Files touched

- `src/aeat/adapters/outbound/llm/test_cache.py` (extended + canary path fix)

## Collision check

Clean — `git diff` on target file returned empty before first edit.

## Test outcome

42/42 tests pass including all new tests.
