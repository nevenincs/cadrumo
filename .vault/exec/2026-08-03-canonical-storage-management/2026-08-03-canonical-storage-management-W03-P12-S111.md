---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:139f42101dfda0c32b85a300b70559f833205172c41800085137dd1a11d02b42'
step_id: 'S111'
related:
  - "[[2026-08-03-canonical-storage-management-plan]]"
---
<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace canonical-storage-management with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S111 and 2026-08-03-canonical-storage-management-plan placeholders are machine-filled by
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
     The Add an anchor field to StoragePathDefinition naming which directory the grammar's root token means, since three blob grammars anchor it at the blob store's own root_dir while sixteen others mean the storage root, and re-scope the directory-agreement gate to skip or re-anchor the three so it stops certifying an agreement it cannot see, executed against the live resolvers storage_path(StorageCategory.BLOBS) plus the blob-store dirname literal today produce a doubled blobs slash blobs path the gate cannot detect because the two spellings happen to share a name and ## Scope

- `src/cadrumo/adapters/persistence/storage/_storage_path_definitions.py`
- `src/cadrumo/adapters/persistence/storage/tests/test_storage_path_directory_agreement_gate.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

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
