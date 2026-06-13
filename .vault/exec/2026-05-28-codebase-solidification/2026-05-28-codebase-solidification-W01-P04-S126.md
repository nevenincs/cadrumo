---
step_id: S126
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P04.S126 — Renta WEB Open ReplayPayload roundtrip tests

## Outcome

Added three real-behavior roundtrip tests to `test_renta_web_open_oracle.py`:

- `test_replay_payload_roundtrip_via_renta_web_open_driver`: builds canonical JSON
  bytes with casilla observations, validates via `ReplayPayload.model_validate` and
  through `RentaWebOpenReplayDriver.collect_observation`; asserts field and locator
  equality.
- `test_replay_payload_strict_rejects_extra_fields_renta_web_open`: confirms
  `extra="forbid"` raises `ValidationError` on unknown top-level keys.
- `test_replay_payload_strict_rejects_non_string_value_in_observed_renta_web_open`:
  confirms strict `Mapping[str, str]` rejects float values.

No mocks, no skips, no xfail.

## Files touched

- `src/aeat/domain/calculations/registry/test_renta_web_open_oracle.py` (3 tests added)

## Collision check

Clean — `git diff` before first edit returned empty.

## Test outcome

81 tests passed across all three oracle test files: `test_aeat_nif_iva_oracle.py`,
`test_groi_oracle.py`, `test_renta_web_open_oracle.py`.
Commit SHA: `cee49398c`.
