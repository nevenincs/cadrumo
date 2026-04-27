---
tags:
  - '#research'
  - '#test-clave-movil-mark-fix'
date: '2026-04-27'
related:
  - '[[wgergely-aeat-436]]'
  - '[[wgergely-aeat-439]]'
---

# `test-clave-movil-mark-fix` research: Cl@ve Movil test marker hygiene

Issue 436 reports that `src/aeat/auth/test_clave_movil.py` is marked as unit while its authentication-flow tests cover the Cl@ve Movil phone-approval login path. The local checkout currently contains 14 tests in that module and no repository references to the old `--ignore=src/aeat/auth/test_clave_movil.py` workaround.

## Findings

The module was marked with `pytest.mark.unit` and `pytest.mark.domain_aeat_remote`. That access marker is too broad for the whole file because the module includes tests that exercise `ClaveMovilAuthProvider.authenticate()` and `probe_persisted_session()` through fresh-login and resume paths.

The five tests in the current file that cross the Cl@ve login boundary are:

- `test_qr_flow_writes_sidecar_and_storage_state`
- `test_non_qr_fallback_fills_dni_form`
- `test_non_qr_fallback_rejects_missing_fecha`
- `test_probe_uses_existing_sidecar_without_invalidating_on_failure`
- `test_resume_from_fresh_sidecar`

The older issue body names a previous set of five tests: `test_clave_movil_login_success`, `test_clave_movil_login_idempotent_on_repeat_call`, `test_clave_movil_session_expiry_detection`, `test_clave_movil_storage_state_round_trip`, and `test_clave_movil_session_idle_deadline_extension`. Those names are not present in the local file, but the current tests above cover the same fresh-login, persistence, probe, and resume behaviors.

The leak mechanism is the provider's browser-driven Cl@ve flow, not a separate `aiohttp` or `httpx` side channel. In the current provider, `_fresh_login_locked()` creates a browser context, navigates to AEAT's selector URL, clicks into Cl@ve Movil, prints the approval banner, and polls `_wait_for_post_auth_landing()` until the post-auth AEAT target appears. The hand-written `_FakeBrowserSession` intercepts this path today by supplying `_FakeContext` and `_FakePage` methods, but the behavior under test is still a live AEAT authentication flow with human approval semantics. The stand-in is coupled to the provider's page-driving details and does not make the module a true unit surface under the project's marker taxonomy.

No provider-internal raw HTTP client was found in `ClaveMovilAuthProvider`; `_resolve_browser_session()` either uses the supplied `BrowserSessionLike` or requires an injected browser-session factory. The remote boundary is therefore the Cl@ve browser/session path itself.

Path A, re-marking the module as `live_read`, matches the pytest marker rules: module-level access marker only, read-side AEAT domain, and no mocks/cassettes. Path B would require adding recorded sessions or cassettes, which conflicts with the project ban on `vcr`, `pytest_httpx`, mocks, fakes, and shortcuts for passing tests.

The documentation cleanup search found no current `--ignore=src/aeat/auth/test_clave_movil.py` references in `justfile`, `.github/workflows`, `docs`, `tests/README.md`, `src/aeat`, or `.vaultspec/rules/rules`.
