---
step_id: S174
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-07-17'
body_hash: 'sha256:35ca5c4817c85a63d2b528361f7634985474e103c7b620bdca5a50f91c34e082'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-27-centralized-module-drift-audit]]'
---

# codebase-solidification W01.P07.S174 — OracleEnvironment round-trip tests

## Outcome

Extended `src/aeat/domain/calculations/registry/test_live_parity.py` with
five new real-behavior tests under the "S174: OracleEnvironment StrEnum
round-trip" block:

- `test_oracle_environment_members_are_str_subclass` — asserts every member
  is a str instance (StrEnum contract).
- `test_oracle_environment_member_values` — parametrized over all three
  members, asserting `member == expected_value` and `str(member)`.
- `test_oracle_environment_default_round_trips_through_catalogue_register` —
  full `register(PRODUCTION) → lookup()` cycle via enum member.
- `test_oracle_environment_test_environment_round_trips_through_catalogue`
- `test_oracle_environment_both_round_trips_through_catalogue`

## Files touched

- `src/aeat/domain/calculations/registry/test_live_parity.py`

## Verification

77 tests pass. Commit: 2f51c3e0d. `vault plan step check S174` applied.
