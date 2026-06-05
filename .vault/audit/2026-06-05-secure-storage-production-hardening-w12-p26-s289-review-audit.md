---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` Code Review

## S289-001 | PASS | Access-gate facade is not a storage backend

`src/aeat/core/access_gate/__init__.py` exports the live-read gate, live-write refusal,
authorization-manifest types, and loader helpers. It does not resolve active buckets,
open secure-object repositories, write SQL routes, scan profile manifests, call remote
providers, or handle master-key material. The package's plaintext files are limited to
authorization manifest fragments loaded by the sibling authorization module through
the shared TOML helper.

Disposition: close `AFR-187` as a plaintext-exception facade and gate policy surface.

## S289-002 | PASS | AEAT environment state flows through Settings

The live-read gate reads AEAT live-test opt-in from the injected
`aeat.core.config.Settings` instance and renders the canonical environment variable
name through `LIVE_READ_TEST_OPT_IN_ENV_VAR`. The legacy local literal was removed.
The only direct environment read left in this module is `PYTEST_CURRENT_TEST`, a pytest
runner marker with no AEAT settings field; tests can pass it through the explicit
`pytest_current_test` seam instead of mutating the real environment.

## S289-003 | PASS | Exceptions use the AEAT hierarchy and registry

The access-gate errors derive from `AeatError` through `src/aeat/core/access_gate/_errors.py`.
`LiveSubmitForbiddenError`, `AeatLiveReadNotEnabledError`, and
`AuthorizationManifestError` are registered in the central error registry.
Authorization manifest failures have locale entries in all audited locales, and live
submit refusal carries a translated-message key for direct CLI rendering.

## S289-004 | PASS | Exception propagation is explicit

`require_live_read()` raises `AeatLiveReadNotEnabledError` only for pytest-driven live
reads when `Settings.aeat_live_tests_enabled` is not exactly `"1"`. Operator contexts
fall through to the auth/profile/read-only guards. `require_live_write()` always raises
`LiveSubmitForbiddenError`. Authorization manifest parsing raises
`AuthorizationManifestError` for malformed present fragments and uses
default-deny-by-absence only when the manifest directory is absent.

## S289-005 | PASS | Duplication and tests

Vaultspec RAG clustered this slice with the settings override tests, outbound auth gate
tests, auth operator login gate, authorization manifest loader, and error registry
entries. No duplicate live-read gate or plaintext authorization manifest facade was
found in the reviewed cluster. The focused tests use the real settings override
surface, real gate object, and real authorization manifest loader; they do not
monkeypatch, stub, skip, xfail, or mirror gate logic.

Validation passed:

- `uv run --no-sync ruff check src/aeat/core/access_gate/__init__.py src/aeat/core/access_gate/_authorization.py src/aeat/core/access_gate/_errors.py src/aeat/core/access_gate/test_override.py src/aeat/core/access_gate/test_authorization_manifest.py src/aeat/adapters/outbound/aeat/auth/test_gate.py src/aeat/application/auth/_operator.py src/aeat/core/errors/registry/_core.py`
- `uv run --no-sync pytest -q src/aeat/core/access_gate/test_override.py src/aeat/core/access_gate/test_authorization_manifest.py src/aeat/adapters/outbound/aeat/auth/test_gate.py src/aeat/entrypoints/cli/test_registry_cli.py::test_list_filed_data_cli_requires_live_gate_before_remote_read src/aeat/entrypoints/cli/test_registry_cli.py::test_capture_filed_data_cli_requires_live_gate_before_local_writes src/aeat/entrypoints/cli/test_registry_cli.py::test_capture_iva_history_cli_requires_live_gate_before_local_writes src/aeat/entrypoints/cli/test_registry_cli.py::test_capture_source_filed_data_requires_live_gate_before_local_writes`
- `uv run --no-sync pytest -q src/aeat/entrypoints/cli/_config/test_auth_round5_surface.py::test_login_refuses_with_user_prose_citing_live_tests_gate src/aeat/entrypoints/cli/_config/test_auth_round5_surface.py::test_operator_login_without_pytest_context_does_not_require_live_test_gate`
- `uv run --no-sync -q python -m aeat.locales audit`
- `uv run --no-sync vaultspec-rag search "AeatAccessGate settings live read opt in PYTEST_CURRENT_TEST os.environ authorization manifest plaintext exception" --type code --port 8766 --max-results 8`
- `uv run --no-sync vaultspec-rag search "access gate AuthorizationManifestError AeatError read_toml default deny authorization.d manifest exception handling" --type code --port 8766 --max-results 8`
