---
tags:
  - "#plan"
  - "#cert-provider"
date: 2026-04-18
modified: '2026-04-18'
related:
  - "[[2026-04-18-cert-provider-migration-adr]]"
  - "[[2026-04-18-cert-provider-migration-research]]"
---
# cert-provider-migration-plan

## Goal
Implement the `AuthProvider` protocol and move existing PKCS#12 logic into `CertificateAuthProvider` per `#282` and `#281`.

## Steps

1. **Protocol and Model Definition**
   - Create `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_protocols.py` containing `AuthProvider`, `AuthProviderKind` (enum), `AuthProviderDescription` (for describe method).
   - Update `AeatSession` in `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_authenticator.py` (or move it to a central models file) to include the `provider_detail` discriminator, creating `CertificateSessionDetail`. `certificate_nif` becomes `identity_nif`.

2. **Move Files**
   - Create directory `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_providers/_certificate/`.
   - Move `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/certificate.py` -> `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_providers/_certificate/certificate.py`.
   - Move `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_certificate_backends/` -> `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_providers/_certificate/_certificate_backends/`.
   - Update imports in the moved files (e.g. adjust relative imports).

3. **Implement CertificateAuthProvider**
   - Create `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/_providers/_certificate/provider.py`.
   - Extract the certificate loading and logic from `AeatAuthenticator` into `CertificateAuthProvider`.
   - `CertificateAuthProvider.authenticate()` will return the new `AeatSession`.
   - `BrowserContextProvisioner` needs to be defined and implemented for injecting `client_certificates` into Playwright's `new_context`.

4. **Update Facade and References**
   - Update `AeatAuthenticator` to use `AuthProvider`.
   - Alternatively, rename `AeatAuthenticator` to something that delegates to `AuthProvider`, or replace it entirely. The prompt requires us to "reframe existing cert code under AuthProvider protocol".
   - Fix all imports of `load_certificate`, `certificate.py`, etc., across `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/__init__.py`.

5. **Test Updates**
   - Fix test paths and imports in `tests/test_authenticator.py` and `tests/test_certificate.py`.
   - Ensure the `test_authenticator.py` mocks map correctly to the new protocol shape and that the tests pass.

6. **Validation**
   - Run `just test` or `pytest` to verify.
