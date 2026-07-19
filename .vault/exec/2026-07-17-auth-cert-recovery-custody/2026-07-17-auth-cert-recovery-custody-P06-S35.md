---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-17'
modified: '2026-07-19'
step_id: 'S35'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

# Remove certificate backend selectors from every payload and schema projection while preserving independent master-key keyring custody contracts

## Scope

- `src/cadrumo/entrypoints/cli/_config_payloads.py`

## Description

Removed the last certificate-backend projection from every payload and schema surface in one atomic relocation (`relocation:SECURE_STORAGE_BACKEND_LABEL`, commit `c4a8166ab4`), while leaving the independent master-key OS-keyring custody untouched. Since the certificate keyring backend was deleted in P02, named certificate secrets have exactly one storage authority, so the constant `secure_storage` backend descriptor was a compatibility shadow reporting a choice that no longer exists.

- Dropped the `backend` field from the JSON payload `CertificateSourceSecretMutationPayload` (`_config_payloads.py`) and its mirrored application result `CertificateSourceSecretMutationResult` (`_operator_results.py`).
- Removed the two `backend=SECURE_STORAGE_BACKEND_LABEL` result constructions and the certificate-secret-set/rotate/remove event-payload `"backend"` key from `_certificate_sources_operator.py`, and the two `backend\t{result.backend}` operator emit lines from the `_certificate.py` CLI door.
- Deleted the `SECURE_STORAGE_BACKEND_LABEL` constant from `_certificate_secret_backend.py` and its re-exports from that module's `__all__` and the `application.auth` facade `__init__.py`; reconciled the `test_certificate_secret_backend.py` assertions to prove the descriptor is absent rather than equal to `secure_storage`.

## Outcome

Step complete. The certificate-secret contract now projects only name/presence/rotated/removed — no backend descriptor. Gates green: ruff clean; collect-only clean (226 tests); `test_certificate_secret_backend.py` + `test_json_schema_conformance.py` (173 passed); serial `test_certificate.py` (13 passed); the full `application/auth/tests` suite (172 passed). Committed as `c4a8166ab4`.

## Notes

The `CADRUMO_SECRET_STORE_BACKEND` master-key custody references in the help surface are a distinct, preserved contract and were deliberately left intact per the step's "preserve independent master-key keyring custody" constraint. Real-behavior tests only; the event-commit failure path is forced by a real SQLite trigger, no mock. During staging a peer's `test_bundle_export_authority.py` was already in the shared index; it was excluded from this commit via explicit pathspec and left staged for its owner.
