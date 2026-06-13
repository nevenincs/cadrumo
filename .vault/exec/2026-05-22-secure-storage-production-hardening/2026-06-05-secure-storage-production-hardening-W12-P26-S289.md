---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S289'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S289 - Close AFR-187 for access-gate exports

Scope: close `AFR-187` for `src/aeat/core/access_gate/__init__.py` with signals
`plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`.

## Description

- Audited the access-gate public surface, live-read/write gate, exception exports,
  and authorization manifest exports.
- Confirmed `AeatAccessGate` is a live policy boundary, not a secure bucket/profile
  runtime repository factory.
- Confirmed AEAT live-test configuration is consumed through `Settings` and
  `override_settings`; the only direct environment read is the pytest runner marker
  `PYTEST_CURRENT_TEST`, documented as non-AEAT infrastructure state.
- Confirmed the authorization manifest loader remains a retained plaintext TOML
  exception boundary using the shared `read_toml()` helper and typed
  `AuthorizationManifestError` failures.
- Replaced the legacy access-gate-local live-submit locale override with the
  centralized `errors.locked.locked_access_gate_live_submit_forbidden` key used by
  the error registry.
- Removed the obsolete `access_gate.errors.default_translatable` locale leaf through
  `python -m aeat.locales`, then reconciled locale files with `python -m aeat.locales
  scaffold`.
- Added behavior coverage proving `LiveSubmitForbiddenError` renders through the
  centralized error-registry/i18n path.
- Ran focused ruff, behavior tests, locale audit, and vaultspec RAG search.

## Outcome

`AFR-187` is closed as a retained plaintext exception and policy-export boundary.
No bucket or profile interface is hidden behind `src/aeat/core/access_gate/__init__.py`;
runtime storage enrollment remains in the storage runtime factories and live flows that
call the gate before remote reads. The live-submit refusal now uses the central error
registry locale key rather than a deprecated access-gate-local translation namespace.

Validation passed:

- `uv run --no-sync ruff check src/aeat/core/access_gate/__init__.py src/aeat/core/access_gate/_errors.py src/aeat/core/access_gate/_authorization.py src/aeat/core/access_gate/test_override.py src/aeat/core/access_gate/test_authorization_manifest.py src/aeat/adapters/outbound/aeat/auth/test_gate.py src/aeat/entrypoints/cli/test_windows_encoding.py src/aeat/entrypoints/cli/test_error_registry_contract.py src/aeat/core/errors/test_registry.py`
- `uv run --no-sync pytest -q src/aeat/core/access_gate/test_override.py src/aeat/core/access_gate/test_authorization_manifest.py src/aeat/adapters/outbound/aeat/auth/test_gate.py src/aeat/entrypoints/cli/test_windows_encoding.py src/aeat/entrypoints/cli/test_error_registry_contract.py src/aeat/core/errors/test_registry.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-rag search "AeatAccessGate Settings live read authorization manifest read_toml no secure bucket repository runtime" --type code --port 8766 --max-results 8`

## Notes

The access-gate module still contains a direct `os.environ` read for
`PYTEST_CURRENT_TEST`. This is intentionally retained as a pytest infrastructure
marker and is covered by real settings-override tests proving AEAT configuration
does not bypass `Settings`.
