---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
step_id: 'S289'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S289 - Close AFR-187 for access-gate facade

Scope: close `AFR-187` for `src/aeat/core/access_gate/__init__.py` with signals
`plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`.

## Description

- Audited the access-gate facade, live-read gate, live-write refusal, and exported
  authorization manifest loader symbols.
- Preserved the shared worktree change that routes AEAT live-test opt-in naming
  through the central config constant and `Settings` value.
- Confirmed direct environment access is limited to pytest's own `PYTEST_CURRENT_TEST`
  marker and has an explicit test seam.
- Confirmed access-gate exceptions derive from the core AEAT error base and are
  covered by the central error registry.
- Confirmed authorization manifest loading is a plaintext TOML declaration boundary
  that fails loudly for malformed present fragments and default-denies only when the
  manifest directory is absent.
- Ran vaultspec RAG semantic search for duplicated gate, manifest, and exception
  handling surfaces.
- Closed `W12.P26.S289` through `vaultspec-core vault plan step check` and updated
  the `AFR-187` register status to `closed`.

## Outcome

`AFR-187` is closed as a plaintext-exception access-gate facade. The facade remains
outside runtime secure bucket repository selection while preserving the centralized
settings path for AEAT live-read test opt-in and the typed access-gate error surface.

Validation passed:

- `uv run --no-sync ruff check src/aeat/core/access_gate/__init__.py src/aeat/core/access_gate/_authorization.py src/aeat/core/access_gate/_errors.py src/aeat/core/access_gate/test_override.py src/aeat/core/access_gate/test_authorization_manifest.py src/aeat/adapters/outbound/aeat/auth/test_gate.py src/aeat/application/auth/_operator.py src/aeat/core/errors/registry/_core.py`
- `uv run --no-sync pytest -q src/aeat/core/access_gate/test_override.py src/aeat/core/access_gate/test_authorization_manifest.py src/aeat/adapters/outbound/aeat/auth/test_gate.py src/aeat/entrypoints/cli/test_registry_cli.py::test_list_filed_data_cli_requires_live_gate_before_remote_read src/aeat/entrypoints/cli/test_registry_cli.py::test_capture_filed_data_cli_requires_live_gate_before_local_writes src/aeat/entrypoints/cli/test_registry_cli.py::test_capture_iva_history_cli_requires_live_gate_before_local_writes src/aeat/entrypoints/cli/test_registry_cli.py::test_capture_source_filed_data_requires_live_gate_before_local_writes`
- `uv run --no-sync pytest -q src/aeat/entrypoints/cli/_config/test_auth_round5_surface.py::test_login_refuses_with_user_prose_citing_live_tests_gate src/aeat/entrypoints/cli/_config/test_auth_round5_surface.py::test_operator_login_without_pytest_context_does_not_require_live_test_gate`
- `uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-rag search "AeatAccessGate settings live read opt in PYTEST_CURRENT_TEST os.environ authorization manifest plaintext exception" --type code --port 8766 --max-results 8`
- `uv run --no-sync vaultspec-rag search "access gate AuthorizationManifestError AeatError read_toml default deny authorization.d manifest exception handling" --type code --port 8766 --max-results 8`

## Notes

This step intentionally keeps `PYTEST_CURRENT_TEST` outside `Settings`; it is pytest
runner infrastructure, not AEAT configuration. The next secure-storage ledger row,
`src/aeat/core/config.py`, remains the broader settings and environment authority
review.
