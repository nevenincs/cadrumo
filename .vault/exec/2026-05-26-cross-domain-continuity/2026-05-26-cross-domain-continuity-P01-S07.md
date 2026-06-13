---
step_id: S07
date: 2026-05-27
modified: '2026-05-27'
tags:
  - "#exec"
  - "#cross-domain-continuity"
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
commit: 0b2f1e4b1
---

# cross-domain-continuity P01.S07 — real-CLI boundary tests

## Deliverables

- `src/aeat/entrypoints/cli/test_errors_boundary.py` (new) — 3 real-CLI tests, no mocks:
  - `test_drifted_stored_profile_surfaces_stored_data_boundary_message`: seeds profile, corrupts persisted JSON (ACTIVE + removed_at), invokes `config profile show`, asserts `config repair` present and `command input failed validation` absent.
  - `test_drifted_stored_profile_boundary_is_distinct_from_unexpected_error`: same corruption, asserts `aeat.diagnostics` absent.
  - `test_malformed_cli_input_surfaces_input_time_validation_boundary`: `ledger add --date not-a-date`, asserts stored-data message absent.

## Key design decisions

- Uses `isolated_runtime_profile` (real KEK/DEK, `activate_session` ContextVar) instead of `AEAT_SECRET_STORE_BACKEND=unsecured` — the latter fails `require_ready()` at the `unsecured_backend` check. The `CliRunner` inherits ContextVars from the test thread so `load_settings()` and `_active_session` resolve correctly inside CLI invocations.
- Seeds directly via `UserProfileLifecycleRepository.save` (bypassing `ProfileRepository.create` which would refuse the already-provisioned manifest).
- Corrupts via `runtime_profile.repository` using the same load/mutate/save pattern as `test_repository_roundtrip.py`.

## Outcome

All 3 tests pass. Ruff and pyright clean.
