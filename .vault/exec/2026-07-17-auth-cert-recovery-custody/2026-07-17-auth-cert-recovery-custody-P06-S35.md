---
tags:
  - '#exec'
  - '#auth-cert-recovery-custody'
date: '2026-07-17'
modified: '2026-07-17'
step_id: 'S35'
related:
  - "[[2026-07-17-auth-cert-recovery-custody-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace auth-cert-recovery-custody with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S35 and 2026-07-17-auth-cert-recovery-custody-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Remove certificate backend selectors from every payload and schema projection while preserving independent master-key keyring custody contracts and ## Scope

- `src/cadrumo/entrypoints/cli/_config_payloads.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
