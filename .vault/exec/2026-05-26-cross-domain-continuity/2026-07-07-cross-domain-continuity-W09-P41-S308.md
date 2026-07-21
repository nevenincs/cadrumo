---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-07'
modified: '2026-07-17'
step_id: 'S308'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-05-27-profile-portability-adr]]"
---

# R8-NURIA-MODERATE encrypted profile-bundle transfer path

## Scope

- `bundle export contains cleartext NIF name surnames LOPD risk for gestor sending bundles via email`
- `encrypt the bundle payload using a recipient-key or passphrase`
- `preserve existing schema/versioning`
- `src/aeat/application/user_profile/`

## Decision

S308 is closed by the `config profile export` / `config profile import` surface
itself, not by pointing operators only at sealed bucket archives.

- `UserProfilePortableExport` remains the v3 typed payload.
- `config profile export --passphrase ...` serializes the
  `UserProfilePortableExport` JSON bytes, derives an Argon2id key from the
  operator passphrase, and AEAD-encrypts those serialized payload bytes into a
  transport envelope.
- `config profile import PATH --passphrase ...` decrypts that envelope first,
  then runs `UserProfilePortableExport.model_validate_json(...)` and the existing
  supported-bundle-schema gate before provisioning or restoring any profile data.
- `config profile export --cleartext-local` is the explicit local/SAR JSON escape
  hatch. Implicit cleartext export is refused.

This preserves bundle schema semantics: encryption wraps the serialized payload
instead of mutating `UserProfilePortableExport` into an incompatible fake shape.
The archive path remains the full-custody backup/recovery transport, but S308's
gestor transfer route is now the encrypted structured bundle path on `profile
export --passphrase`.

## Grounding

- Required vault RAG search found the S308 plan row and the R8-NURIA audit finding:
  cleartext NIF/name/surnames in bundle export was the LOPD risk; passphrase
  encryption was the requested mitigation.
- Required code RAG search found the current v3 bundle serializer/deserializer,
  the `config profile export/import` cleartext surface, and the sealed archive
  implementation under `BucketMaintenanceService`.
- AEPD cryptographic-systems guidance (May 2023) frames encryption as a GDPR
  personal-data security risk mitigation and stresses validating the cryptographic
  system, not just choosing an algorithm.
- GDPR Article 32/34, as published by BOE, names encryption as an appropriate
  technical measure and treats data made unintelligible to unauthorized persons
  as a breach-impact mitigator.

This is engineering/security grounding, not legal advice.

## Changes

- Added `application.user_profile` passphrase bundle encryption helpers that
  reuse existing storage primitives: `KdfParams.default()` / Argon2id
  `derive_kek_with_params`, plus `encrypt_record` / `decrypt_record`.
- Added `config profile export --passphrase` and `config profile import
  --passphrase` for encrypted structured bundle transfer.
- Made cleartext structured JSON export explicit with `--cleartext-local`; the
  cleartext warning now points to `aeat config profile export --passphrase ...`
  for encrypted structured transfer.
- Kept `UserProfilePortableExport` unchanged. The encrypted file is a transport
  envelope around the serialized payload; validation and schema-version checks run
  only after decrypt.
- Added/updated real CLI tests for encrypted roundtrip, no raw NIF/name/surname
  or profile label in the encrypted export file, wrong-passphrase refusal without
  traceback, explicit cleartext/SAR warning, import idempotency, lifecycle import,
  and setup roundtrip callers that deliberately need cleartext JSON.
- Kept the existing archive warning/archive tests from the prior WIP; archive
  remains the full-backup path, while encrypted `profile export --passphrase` is
  the S308 structured-transfer path.

## Validation

Passed:

- `uv run --no-sync pytest -q src/aeat/entrypoints/cli/tests/test_profile_export_roundtrip.py::test_v3_bundle_passphrase_encrypted_export_import_roundtrip src/aeat/entrypoints/cli/tests/test_profile_export_roundtrip.py::test_v3_bundle_encrypted_import_refuses_wrong_passphrase_without_traceback src/aeat/entrypoints/cli/tests/test_profile_export_roundtrip.py::test_export_emits_cleartext_sensitivity_warning_notice src/aeat/entrypoints/cli/tests/test_profile_export_roundtrip.py::test_export_requires_explicit_cleartext_or_passphrase -m "integration and hex_entrypoint"`
- `uv run --no-sync pytest -q src/aeat/entrypoints/cli/tests/test_profile_export_roundtrip.py -m "integration and hex_entrypoint"`
- `uv run --no-sync pytest -q src/aeat/entrypoints/cli/tests/test_profile_import_idempotency.py -m "integration and hex_entrypoint"`
- `uv run --no-sync pytest -q src/aeat/entrypoints/cli/tests/test_profile_lifecycle_navigation.py::test_profile_import_label_refuses_duplicate_bundle_identity src/aeat/application/setup/tests/test_atomic_create_roundtrip.py::test_atomic_create_roundtrip_export_import_preserves_label_and_facts -m "integration or hex_entrypoint or unit or hex_application"`
- `uv run --no-sync pytest -q src/aeat/entrypoints/cli/tests/test_profile_archive_roundtrip.py -m "integration and hex_entrypoint"`
- `uv run --no-sync ruff check src/aeat/application/user_profile/_bundle_encryption.py src/aeat/application/user_profile/__init__.py src/aeat/entrypoints/cli/_config/_profile_bundle.py src/aeat/entrypoints/cli/tests/test_profile_export_roundtrip.py src/aeat/entrypoints/cli/tests/test_profile_import_idempotency.py src/aeat/entrypoints/cli/tests/test_profile_lifecycle_navigation.py src/aeat/application/setup/tests/test_atomic_create_roundtrip.py`
- `uv run --no-sync vaultspec-core vault check features --feature cross-domain-continuity`
- `uv run --no-sync vaultspec-core vault check frontmatter`

Blocked by unrelated locale catalogue drift:

- `uv run --no-sync python -m aeat.locales scaffold --check`
- `uv run --no-sync python -m aeat.locales audit`

Both locale commands fail before/after this slice with the same unrelated extra
key in all four catalogues:
`cli.overview.warning.m303_simplificado_forfait_unavailable`.

Earlier attempted commands `uvx vault feature check cross-domain-continuity` and
`uvx vault frontmatter check` resolved the unrelated PyPI `vault` package and
failed while building `mysqlclient`; the valid project command is
`uv run --no-sync vaultspec-core ...`, which passed as listed above.

## Outcome

S308 is honestly closed. The gestor email/cross-host structured-transfer route is
`aeat config profile export --passphrase ...` plus `aeat config profile import
PATH --passphrase ...`. The cleartext export remains only as
`--cleartext-local` for local/SAR handling and carries a loud typed warning with
no claim that it is suitable for transfer.
