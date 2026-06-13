---
tags:
  - '#research'
  - '#test-clave-movil-mark-fix'
date: '2026-04-27'
modified: '2026-04-27'
related: []
---

# `test-clave-movil-mark-fix` research: Cl@ve Movil test marker hygiene

Issue 436 reported that `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_clave_movil.py` was marked as unit while its tests appeared to cover the Cl@ve Movil phone-approval login path. Follow-up review corrected that premise: the local tests use hand-written browser-session stand-ins and do not authenticate against AEAT or require operator Cl@ve approval.

## Findings

The module is a protocol-level test surface: `pytest.mark.unit` remains the correct access marker because the browser/session objects are local stand-ins. `pytest.mark.domain_aeat_remote` remains useful as the domain marker because the provider contract models AEAT Sede authentication.

The tests that model the Cl@ve provider flow are:

- `test_qr_flow_writes_sidecar_and_storage_state`
- `test_non_qr_fallback_fills_dni_form`
- `test_non_qr_fallback_rejects_missing_fecha`
- `test_probe_uses_existing_sidecar_without_invalidating_on_failure`
- `test_resume_from_fresh_sidecar`

The older issue body names a previous set of five tests: `test_clave_movil_login_success`, `test_clave_movil_login_idempotent_on_repeat_call`, `test_clave_movil_session_expiry_detection`, `test_clave_movil_storage_state_round_trip`, and `test_clave_movil_session_idle_deadline_extension`. Those names are not present in the local file, but the current tests above cover the same fresh-login, persistence, probe, and resume behaviors.

The earlier analysis treated this as crossing the real Cl@ve boundary. That was incorrect for the test module: `_FakeBrowserSession`, `_FakeContext`, and `_FakePage` intercept the browser path entirely. These tests check provider control flow and persistence behavior against the browser protocol; they do not prove a live AEAT session and must not be used as evidence that AEAT authentication passed.

No provider-internal raw HTTP client was found in `ClaveMovilAuthProvider`; `_resolve_browser_session()` either uses the supplied `BrowserSessionLike` or requires an injected browser-session factory.

The provider previously auto-submitted AEAT's `DialogoRepresentacion` representation form after Cl@ve approval. That is a remote form submission and is no longer acceptable as an automatic provider action. The corrected provider refuses that page instead of clicking through.

The documentation cleanup search found no current `--ignore=src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_clave_movil.py` references in `justfile`, `.github/workflows`, `docs`, `tests/README.md`, `src/aeat`, or `.vaultspec/rules/rules`.
