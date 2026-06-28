---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S200'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s200-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S200`

Closed `AFR-098` for IVA compensation history and cross-committed the
localized exception hardening found during supervisor review.

## Description

- Reviewed `src/aeat/application/calculations/_iva_compensation_history.py`
  against the `runtime-default` classification for secure-bound storage.
- Verified `IvaCompensationHistoryRepository` inherits the centralized
  `SecureBoundRepository` and uses the registered IVA compensation history
  namespace, sensitivity, and schema version.
- Verified runtime migration coverage includes missing active-session refusal,
  route/session mismatch refusal, and active-profile isolation for IVA
  compensation history records.
- Replaced raw formatted IVA compensation history errors with registered
  `translated_message` keys and structured context for year-range, seed
  conflict, Modelo-boundary, and decimal parse failures.
- Aligned the adjacent pure carry-forward year-range guard with the same
  registered localized error class.
- Removed the raw fallback message from the live IVA history capture boundary;
  it now relies on its existing locale key with structured context.
- Cross-committed intersecting live IVA hardening already present in the shared
  worktree for `src/aeat/application/live/__init__.py`: standalone IVA capture
  entrypoints now execute inside the active-profile storage span, and persisted
  acquisition failure context applies diagnostic redaction to sensitive keys.
- Updated IVA compensation and CLI tests to assert typed exception metadata
  instead of preserving deprecated English message matching.
- Added locale leaves through the canonical `python -m aeat.locales` scaffold
  and set commands. The scaffold command also normalized nearby pre-existing
  catalog leaves while preserving locale-audit consistency.

## Outcome

`AFR-098` is closed. IVA compensation history remains profile-local,
secure-bound, and runtime-owned through the shared secure-bound repository
contract. Its application-facing guard errors now use the core localized
exception contract rather than raw ad hoc message strings.

Validation passed:

- `$env:PYTHONPATH='src'; uv run --no-sync -q pytest -q src/aeat/application/calculations/test_iva_compensation_history.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q pytest -q src/aeat/entrypoints/cli/test_iva_wallet_inspector.py::test_seed_iva_compensation_refuses_duplicate`
- `$env:PYTHONPATH='src'; uv run --no-sync -q pytest -q src/aeat/adapters/persistence/storage/test_runtime_migrated_repositories.py -k "iva_compensation_history"`
- `$env:PYTHONPATH='src'; uv run --no-sync -q pytest -q src/aeat/application/test_w04_p21_survivors.py -k "iva_compensation"`
- `$env:PYTHONPATH='src'; uv run --no-sync -q pytest -q src/aeat/application/live/test_filed_capture_calculation_history.py -k "iva_compensation or history"`
- `$env:PYTHONPATH='src'; uv run --no-sync -q pytest -q src/aeat/application/live/test_iva_remote_state_acquisition.py::test_remote_state_capture_refuses_without_active_profile src/aeat/application/live/test_iva_remote_state_acquisition.py::test_standalone_iva_wallet_capture_refuses_without_active_profile src/aeat/application/live/test_iva_remote_state_acquisition.py::test_standalone_iva_history_capture_refuses_without_active_profile src/aeat/application/live/test_iva_remote_state_acquisition.py::test_acquisition_manifest_persists_redacted_auth_diagnostic_ref src/aeat/application/live/test_iva_remote_state_acquisition.py::test_acquisition_manifest_redacts_sensitive_surface_failure_context`
- `uv run --no-sync -q ruff check src/aeat/application/live/__init__.py src/aeat/application/calculations/_iva_compensation_history.py src/aeat/domain/iva_compensation/_carry_forward.py src/aeat/core/errors/registry/_application.py src/aeat/application/calculations/test_iva_compensation_history.py src/aeat/entrypoints/cli/test_iva_wallet_inspector.py`
- `$env:PYTHONPATH='src'; uv run --no-sync -q python -m aeat.locales audit`

## Notes

The initial S200 record closed the secure-bound storage row without production
edits because repository routing was already compliant. Supervisor review found
an adjacent API-hardening defect: localized exception routing was incomplete for
IVA compensation guard errors. The shared worktree also carried intersecting
live IVA capture/redaction hardening in a file touched by this step, so this
cross-commit records and validates those hunks rather than splitting the file
unsafely. No new direct secure-object repository construction, naked environment
access, silent exception swallowing, `noqa`, `pragma`, monkeypatches, fakes,
mocks, skips, or xfails were introduced.
