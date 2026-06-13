---
step_id: S38
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-28'
modified: '2026-05-28'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
  - '[[2026-05-28-codebase-solidification-W01-P01-S37]]'
---

# codebase-solidification W01.P01.S38 — real-behavior tests for config boundary narrowing

## Outcome

Created `src/aeat/entrypoints/cli/_config/test_config.py` with 8
real-behavior tests exercising the error-boundary narrowing introduced in
S37. All 8 tests pass.

## Test inventory

- `test_aeat_error_from_config_profile_show_unknown_name_emits_typed_envelope`:
  invokes `config profile show NONEXISTENT`; asserts non-zero exit.
- `test_aeat_error_from_config_profile_switch_missing_profile_emits_typed_envelope`:
  invokes `config profile switch no-such-profile`; asserts non-zero exit.
- `test_aeat_error_envelope_is_well_formed_in_json_mode`:
  invokes with `--format json`; asserts non-zero exit and non-empty error payload.
- `test_non_aeat_error_in_profile_show_read_wraps_to_config_boundary_error`:
  injects `RuntimeError` via `monkeypatch.setattr` into `_read_profile_record`;
  asserts exit code 2 and "profile_record_unreadable" in output.
- `test_non_aeat_error_cause_chain_reaches_config_boundary_error`:
  injects `RuntimeError`; walks exception cause chain to assert
  `ConfigBoundaryError` wraps the raw exception.
- `test_profile_import_with_invalid_json_raises_refused_boundary`:
  writes a non-JSON file; invokes `config profile import`; asserts non-zero exit.
- `test_profile_import_with_structurally_invalid_bundle_surfaces_as_refused`:
  writes valid JSON with wrong schema; asserts non-zero exit.
- `test_config_boundary_error_is_registered_aeat_error_subclass`:
  structural test — instantiates `ConfigBoundaryError`, asserts it is an
  `AeatError` and `get_registered_error_code` returns `ERROR_CONFIG_BOUNDARY`.

## Files touched

- `src/aeat/entrypoints/cli/_config/test_config.py` (new)

## Quality gates

- `pytest src/aeat/entrypoints/cli/_config/test_config.py`: 8 passed
- `ruff check`: all checks passed
