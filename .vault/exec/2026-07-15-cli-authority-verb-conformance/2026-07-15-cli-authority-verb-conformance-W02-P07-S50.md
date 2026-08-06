---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-17'
modified: '2026-07-17'
body_hash: 'sha256:7960135441d7584dd430ba5b617ea4b1f7031364146ab032640fb8855268251f'
step_id: 'S50'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Make the certificate authenticator and adapter provider factory consume the resolved typed active certificate credential directly, eliminating their independent path and password projection from Settings

## Scope

- `src/cadrumo/adapters/outbound/aeat/auth/_authenticator.py`
- `src/cadrumo/adapters/outbound/aeat/auth/__init__.py`
- `src/cadrumo/adapters/outbound/aeat/auth/tests`

## Description

- Confirm the certificate authenticator consumes the resolved typed active certificate credential directly, with no independent path or password projection from Settings.
- Confirm the adapter provider factory requires and forwards the resolved certificate credential when constructing the certificate provider.

## Outcome

Verified complete against the committed tree. `AeatAuthenticator.__init__` requires `credentials: ActiveCertificateCredentials`; `_require_bundle` and `describe` read the certificate path, password, and friendly name only from `self._credentials`, not from Settings fields. The adapter factory `select_provider` refuses certificate construction without `certificate_credentials` and passes the typed credential straight through. The adapter authenticator suites are green: `uv run --no-sync pytest src/cadrumo/adapters/outbound/aeat/auth/tests/test_authenticator_part1.py test_authenticator_part2.py test_auth_provider_real_lifecycle.py test_health.py test_certificate.py -q` reports 64 passed.

## Notes

The authenticator's credential-consumption refactor landed in the W02.P07 credential-unification wave (commit `f5273bda59` and the subsequent in-flight freeze snapshots); this step is closed as verified-complete with its real-behavior adapter suites green rather than by an additional source commit.
