---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-17'
modified: '2026-07-17'
body_hash: 'sha256:753c9c4118b8bda4d4a2c893604b369e0a3cae25364832661865d5f93731e620'
step_id: 'S47'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Delete the certificate keyring backend, backend-kind selector, factory branch, exports, and certificate-specific keyring service and account code while retaining secure storage as the only certificate-secret backend and preserving independent master-key OS-keyring custody

## Scope

- `src/cadrumo/application/auth/_certificate_secret_backend.py`
- `src/cadrumo/application/auth/__init__.py`

## Description

- Confirm the certificate keyring backend, backend-kind selector, factory branch, exports, and certificate-specific keyring service and account code are deleted from `_certificate_secret_backend.py`.
- Confirm the `application.auth` facade re-exports only the secure-storage backend, its protocol, and the stable label, with no keyring surface.
- Confirm the independent master-key OS-keyring custody backend is untouched.

## Outcome

Verified complete against the committed tree. The certificate keyring alternative was deleted in commit `f5273bda59` ("refactor(auth): unify certificate credentials on secure storage; delete keyring backend"), landed under the W02.P07 credential-unification work. `_certificate_secret_backend.py` now exposes exactly `SECURE_STORAGE_BACKEND_LABEL`, `CertificateSecretBackend`, and `SecureStorageCertificateSecretBackend`; a repository-wide search finds no `KeyringCertificateSecretBackend`, `CertificateSecretBackendKind`, backend factory, or backend selector in production auth code. The retired-symbol absence gates in `test_certificate_secret_backend.py` are green.

## Notes

The substantive deletion landed in a peer commit as part of the S48/S49 credential-unification wave; this step is closed as verified-complete with its enforcing absence tests green rather than by an additional deletion commit. The only surviving keyring references in the auth package are prose confirming absence, the retained master-key OS-keyring custody mention, and the test-file absence assertions.
