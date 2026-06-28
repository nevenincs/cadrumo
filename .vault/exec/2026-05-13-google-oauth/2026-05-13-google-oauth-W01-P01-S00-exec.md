---
tags:
  - '#exec'
  - '#google-oauth'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'S00'
related:
  - "[[2026-05-13-google-oauth-plan]]"
  - "[[2026-05-08-google-oauth-adr]]"
---

# `google-oauth` `W01.P01.S00`

Atomic deletion of the post-teardown scaffold under `src/aeat/adapters/outbound/google/` plus removal of every consumer reference that depends on its symbols. After this Step the package is non-importable; subsequent Steps in P01 repopulate it with v1 modules.

- Deleted: `src/aeat/adapters/outbound/google/__init__.py`
- Deleted: `src/aeat/adapters/outbound/google/_paths.py`
- Deleted: `src/aeat/adapters/outbound/google/test_google_auth.py`
- Modified: `src/aeat/core/errors/registry/_adapters.py` (removed `GoogleAuthValidationError` and `GoogleAuthUnavailableError` registry entries)
- Modified: `tests/import_contract/test_adr_layout_import_smoke.py` (removed `aeat.adapters.outbound.google` from `ADR_LAYOUT_PACKAGES` and removed the two `GoogleAuthPath` / `get_credentials_for_scopes` entries from `CANONICAL_PUBLIC_SYMBOLS`)

## Description

The scaffold previously exposed `inspect_google_auth`, `get_credentials_for_scopes`, `GoogleAuthInspection`, `GoogleAuthPath`, `GoogleAuthUnavailableError`, and `GoogleAuthValidationError` as fail-closed stubs. Per the project rule against shims, partial implementations, and dead code, the scaffold and every reference to its symbols ship out atomically rather than persisting through subsequent P01 Steps.

The defensive negative test `test_aeat_auth_does_not_export_google_auth_pipeline` in the smoke-test module is preserved — it asserts that `aeat.adapters.outbound.aeat.auth` does not leak Google symbols, which remains a valid invariant after the scaffold is removed.

The new v1 modules introduced across S03 (`_records.py`), S05 (`_oauth_flow.py`), S08-S09 (`_refresh.py`), S10 (`_errors.py`), and S14 (`_test_oauth_flow.py`) re-establish the package. S11 registers the new typed `GoogleAuthError` hierarchy in the error-code registry. S18's forbidden-import test guards against the scaffold returning.

## Tests

- `uv run ty check src/aeat/core/errors/registry/_adapters.py` passes.
- `uv run pytest tests/import_contract/test_adr_layout_import_smoke.py` passes after the package + symbol entries are removed.
- `uv run pytest src/aeat/adapters/outbound/google/` reports no tests collected (directory empty).
