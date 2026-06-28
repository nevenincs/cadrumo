---
tags: ['#exec', '#live-iva-compensation-wallet']
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S99'
related:
  - '[[2026-05-19-live-iva-compensation-wallet-plan]]'
---


# W10.P24.S99 persisted Clave reuse contract

Scope: Wave W10, Phase P24, Step S99.

## Description

- Stop persisted Cl@ve session probes from using target-specific selector dispatch.
- Keep explicit target selector dispatch available for normal verification/fresh-login paths.
- Add live IVA CLI watchdog context fields for local persisted-session state before and after command timeout.
- Add focused regressions for persisted-probe no-dispatch behavior and watchdog auth diagnostics.

## Outcome

The repeated-auth-request failure is now classified as a real contract defect: the Cl@ve persisted-session probe was documented as never causing fresh login, but explicit target verification could still route through the selector dispatch path. That could create a new phone request instead of merely proving or rejecting the stored session.

The Cl@ve persisted-session probe now verifies the stored landing/default authenticated page without target-specific selector dispatch. If AEAT later rejects the stored session for a specific read surface, that failure belongs to the read surface instead of silently starting another operator-mediated auth request. The direct `verify(session, target_url=...)` path remains unchanged and covered for callers that explicitly need selector dispatch.

The live IVA CLI watchdog timeout now carries redacted local auth-session diagnostics: provider, active-profile status, identity alignment, persisted-session presence, persisted-session expiry, and reaped Playwright process count. This avoids collapsing post-auth filed-history timeouts into ambiguous auth failures.

Validation completed with `uv run --no-sync`:

- `pytest src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py::TestProbePersistedSession::test_probe_with_explicit_target_does_not_click_clave_selector src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py::TestPostAuthLanding::test_verify_clicks_selector_for_explicit_target_probe -q` passed with 2 tests.
- `pytest src/aeat/application/auth/test_ensure_session.py src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py::TestProbePersistedSession src/aeat/entrypoints/cli/test_live_read_subgroups.py::TestIvaRemoteStateCliSurface -q` passed with 14 tests.
- `ruff check src/aeat/application/auth/test_ensure_session.py src/aeat/adapters/outbound/aeat/auth/_clave_movil.py src/aeat/adapters/outbound/aeat/auth/test_clave_movil.py src/aeat/entrypoints/cli/_app_live.py src/aeat/entrypoints/cli/test_live_read_subgroups.py` passed.

No AEAT filing, payment, confirmation, represented-taxpayer selection, or write path was executed.

## Notes

S93 remains open. The live IVA remote-state read still needs a successful read-only filed-history and wallet acquisition with redacted aggregate evidence. The last live command created or refreshed a local persisted Cl@ve session, then timed out in the filed-history surface before producing an acquisition report.
