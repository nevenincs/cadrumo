---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-17'
modified: '2026-07-17'
body_hash: 'sha256:a891e5a9b99bf8e8587b0cb0faa16cb615fda98e88863ff16447bb86863fa2ee'
step_id: 'S06'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

# Delete the certificate keyring backend, backend-kind selector, factory branch, exports, and certificate-specific keyring service and account code while retaining secure storage as the only certificate-secret backend and preserving independent master-key OS-keyring custody

## Scope

- `src/cadrumo/application/auth/_certificate_secret_backend.py`

## Description

This is a reconciliation record. The work it documents was executed under the
originating campaign feature stem before this plan existed; it was not
re-executed here. The originating execution record is the `S47` step record of
the `cli-authority-verb-conformance` campaign, whose action text this step row
carries verbatim.

- Delete the certificate keyring backend, the backend-kind selector, the backend factory branch, and their facade exports.
- Delete the certificate-specific keyring service and account code.
- Retain secure storage as the only certificate-secret backend.
- Preserve the independent master-key operating-system keyring custody backend untouched.

## Outcome

The deletion is real and verifiable in the diff, not merely asserted. Commit
`f5273bda59`, "refactor(auth): unify certificate credentials on secure storage;
delete keyring backend", dated 2026-07-16, removes from
`src/cadrumo/application/auth/_certificate_secret_backend.py` the classes
`KeyringCertificateSecretBackend` and `CertificateSecretBackendKind`, the
exceptions `CertificateSecretNotFoundError` and
`CertificateSecretBackendUnavailableError`, and the `certificate_secret_backend`
factory function, together with all five of their `__all__` entries; the same
commit strips the identical names from the `application.auth` facade's imports
and `__all__`.

At HEAD the module's `__all__` is exactly `CertificateSecretBackend` and
`SecureStorageCertificateSecretBackend`. A repository-wide search for keyring
references in the auth package returns only four hits, all of them prose
confirming absence or naming the retained master-key custody backend: three
docstring lines in the secure-storage backend and certificate-sources modules,
and one comment in the certificate-sources operator. No production keyring
backend, selector, or factory remains.

Enforcement is structural rather than narrative.
`src/cadrumo/application/auth/tests/test_certificate_secret_backend.py` carries
`test_retired_keyring_symbol_absent_from_backend_module`,
`test_retired_keyring_symbol_absent_from_auth_facade`, and
`test_secure_storage_backend_is_the_only_public_backend`, so a reintroduction
reds the suite.

## Notes

The originating record closed this step as verified-complete rather than by an
additional deletion commit, on the grounds that the substantive deletion had
already landed in the credential-unification wave. That framing is confirmed and
is stronger than the record claimed: this reconciliation attributes the deletion
to a specific commit whose diff removes each named symbol, so the step is
substantiated by delivery evidence and not only by end-state inspection.

One drift from the originating record is recorded honestly. That record stated
the module would expose exactly three symbols, including a
`SECURE_STORAGE_BACKEND_LABEL` descriptor. That descriptor no longer exists: a
later peer commit, `c4a8166ab4`, deliberately dropped it as vestigial, and the
backend test module now asserts its absence. The surviving surface is therefore
two symbols, not three. This narrows the public surface further in the
direction this step intended and does not contradict its outcome, but the
originating record's symbol list is stale and should not be read as current.

The master-key operating-system keyring custody backend is a separate concern
and was not touched.
