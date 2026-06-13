---
step_id: S124
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P04.S124 — GROI ReplayPayload roundtrip tests

## Outcome

Added five tests to `test_groi_oracle.py`:

- Fixed `test_replay_driver_rejects_payload_without_observed_object`: updated to
  catch `pydantic.ValidationError` (raised by `ReplayPayload.model_validate`)
  instead of the stale `RegistryValidationError` with match `"observed object"`.
- Fixed `test_replay_driver_rejects_non_string_observed_values`: updated to catch
  `ValidationError` (strict `Mapping[str, str]` enforcement).
- `test_replay_payload_roundtrip_via_groi_driver`: full roundtrip through
  `ReplayPayload.model_validate` and `GroiReplayDriver.collect_observation`.
- `test_replay_payload_strict_rejects_extra_fields`: confirms `extra="forbid"`.
- `test_replay_payload_strict_rejects_non_string_value_in_observed`: confirms
  strict value typing.

No mocks, no skips.

## Files touched

- `src/aeat/domain/calculations/registry/test_groi_oracle.py` (2 fixed + 3 added)

## Collision check

Clean — `git diff` before first edit returned empty.

## Test outcome

All GROI oracle tests pass (including parametrized write-guard invariants).
