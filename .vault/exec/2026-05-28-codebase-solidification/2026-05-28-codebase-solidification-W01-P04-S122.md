---
step_id: S122
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P04.S122 — NIF-IVA ReplayPayload roundtrip tests

## Outcome

Added three real-behavior roundtrip tests to `test_aeat_nif_iva_oracle.py`:

- `test_replay_payload_roundtrip_via_nif_iva_driver`: builds canonical JSON bytes,
  calls `ReplayPayload.model_validate` directly and also through the production
  `AeatNifIvaReplayDriver.collect_observation` path; asserts field equality and
  evidence-locator preservation.
- `test_replay_payload_strict_rejects_extra_fields_nif_iva`: confirms
  `extra="forbid"` raises `ValidationError` on unknown top-level keys.
- `test_replay_payload_strict_rejects_non_string_value_in_observed_nif_iva`:
  confirms strict `Mapping[str, str]` rejects integer values.

No mocks, no skips, no xfail.

## Files touched

- `src/aeat/domain/calculations/registry/test_aeat_nif_iva_oracle.py` (3 tests added)

## Collision check

Clean — `git diff` before first edit returned empty.

## Test outcome

13 tests passed: full `test_aeat_nif_iva_oracle.py` suite.
