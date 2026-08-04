---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:3f16eb775f6d9bebb363a32c04ae376f65638fb2b2fff33a1f451e240b4371be'
step_id: 'S111'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---

# Add an anchor field to StoragePathDefinition naming which directory the grammar's root token means, since three blob grammars anchor it at the blob store's own root_dir while sixteen others mean the storage root, and re-scope the directory-agreement gate to skip or re-anchor the three so it stops certifying an agreement it cannot see, executed against the live resolvers storage_path(StorageCategory.BLOBS) plus the blob-store dirname literal today produce a doubled blobs slash blobs path the gate cannot detect because the two spellings happen to share a name

## Scope

- `src/cadrumo/adapters/persistence/storage/_storage_path_definitions.py`
- `src/cadrumo/adapters/persistence/storage/tests/test_storage_path_directory_agreement_gate.py`

## Description

- Verification only. Implementation landed in an earlier commit: a
  `StoragePathAnchor` enum (`STORAGE_ROOT` / `BLOB_STORE_ROOT`), a required
  `anchor` field on `StoragePathDefinition`, and a `model_validator` refusing
  a `<root>`-kind path definition with a mismatched or missing anchor.
- Confirm every `<root>`-anchored grammar entry declares an `anchor`: sixteen
  `STORAGE_ROOT`, three `BLOB_STORE_ROOT` (`blob_manifest`,
  `blob_content_plaintext`, `blob_content_ciphertext`).
- Confirm the directory-agreement gate is re-scoped to the `STORAGE_ROOT`
  subset via `_storage_root_anchored_definitions()`, and confirm the
  non-vacuity proof (`test_the_blob_store_root_anchor_excludes_three_real_
  entries_not_an_empty_set`) demonstrates the exclusion reaches exactly the
  three real blob keys rather than an accidentally-empty filter.
- Re-run `test_storage_path_directory_agreement_gate.py` at current HEAD: 8
  passed.

## Outcome

Confirmed already landed; no reimplementation performed. The gate no longer
certifies an agreement between two different anchors that happen to share a
literal subdirectory name (`blobs`).

## Notes

None. No skipped work, no scaffolds left in code.
