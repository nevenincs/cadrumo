---
tags:
  - '#adr'
  - '#test-clave-movil-mark-fix'
date: '2026-04-27'
modified: '2026-04-27'
related:
  - '[[2026-04-27-test-clave-movil-mark-fix-research]]'
---

# `test-clave-movil-mark-fix` adr: Keep Cl@ve Movil tests protocol-level | (**status:** `supersedes earlier marker decision`)

## Problem Statement

`src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_clave_movil.py` uses hand-written browser-session stand-ins to drive `ClaveMovilAuthProvider` through login, persistence, probe, and resume paths. Earlier review incorrectly treated those tests as proof of live AEAT/Cl@ve authentication. They are protocol-level unit tests and must not be described as live-auth success.

## Considerations

The affected current tests are `test_qr_flow_writes_sidecar_and_storage_state`, `test_non_qr_fallback_fills_dni_form`, `test_non_qr_fallback_rejects_missing_fecha`, `test_probe_uses_existing_sidecar_without_invalidating_on_failure`, and `test_resume_from_fresh_sidecar`.

The provider path under those tests reaches `_fresh_login_locked()`, where the browser session would navigate AEAT selector URLs with a real browser session. In this module, the local stand-in implements the necessary browser protocol methods and never authenticates to AEAT.

The project marker convention requires module-level access and domain markers. Keeping the whole file as `unit` preserves that rule while accurately describing the execution boundary. The domain remains `domain_aeat_remote` because the provider contract models AEAT Sede behavior.

The searched repository surfaces no longer contain `--ignore=src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_clave_movil.py`, so there is no code or documentation workaround to delete in this checkout.

## Constraints

Live AEAT submission remains permanently forbidden. The no-mocks discipline rules out cassettes, monkeypatching, `vcr`, and HTTP mocking. The provider must also avoid automatic remote form submissions, including representation-selection form submits after Cl@ve approval.

## Implementation

Keep the module-level marker as `pytestmark = [pytest.mark.unit, pytest.mark.domain_aeat_remote]`.

Document at the top of the file that these tests use browser-session stand-ins and do not prove real AEAT authentication or operator Cl@ve approval.

Remove automatic handling of AEAT's `DialogoRepresentacion` representation dispatcher. If AEAT requests that page, the provider raises instead of clicking a submit button.

## Rationale

The corrected decision is chosen because it matches the actual test boundary. Treating stand-in tests as live tests creates false confidence and can mask the fact that AEAT remained unauthenticated.

## Consequences

Default unit selection may run this module because it does not contact AEAT. Any future true live-auth test must use a real browser session, require explicit operator approval, and avoid automatic remote representation-form submission.
