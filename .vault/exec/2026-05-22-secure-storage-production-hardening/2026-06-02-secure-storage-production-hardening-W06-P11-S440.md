---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S440'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-02-secure-storage-production-hardening-w05-p10-s43-review-audit]]'
---

# `secure-storage-production-hardening` `W06.P11.S440`

## Description

- Resolve S43-005 by replacing timestamp-only stale ambiguity with persisted revision ancestry.
- Preserve ancestry across secure-object upserts, raw ciphertext projection, quarantine copies, and remote mirror manifests.
- Keep unknown older root revisions on the conflict path unless their revision id is present in the local ancestry chain.

## Outcome

Closed.

Evidence:

- `secure_objects` now carries `revision_ancestor_ids` as metadata; existing tables receive the column through the repository bootstrap migration.
- `SecureObjectRawRow` exposes the parsed ancestry tuple without decrypting payloads.
- `RemoteMirrorObjectManifest` carries `revision_ancestor_ids`, and `compare_remote_mirror_manifests` treats a remote revision as stale when its id is either the immediate previous revision or any recorded local ancestor.
- Real repository tests now cover a three-save object where the first manifest is correctly classified as `STALE_MIRROR`.
- Real repository tests also cover an unknown older root revision remaining `REVISION_CONFLICT`.
- `uv run --no-sync pytest -q src/aeat/adapters/outbound/storage/test_mirror_manifest.py src/aeat/adapters/outbound/storage/test_foundation.py` passed with 27 tests.
- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/sql/test_secure_objects.py` passed with 41 tests.
- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/crypto/test_encrypted_columns.py src/aeat/adapters/persistence/storage/sql/test_secure_objects.py src/aeat/adapters/persistence/storage/sql/test_archive_bundle_roundtrip.py` passed with 65 tests and 3 pre-existing SQLAlchemy datetime-adapter warnings.
- Targeted Ruff over the storage, mirror, and secure-object ancestry surfaces passed.

## Notes

No plaintext is added to the remote mirror manifest. The ancestry tuple contains revision ids only.
