---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:5d632717edec32ed2370cfa56f6c0673101e0de5ce0abe1513f9b7591d702bd5'
step_id: 'S20'
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
     The S20 and 2026-08-03-canonical-storage-management-plan placeholders are machine-filled by
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
     The Re-point bucket_paths onto the scoped accessor, gated by the existing bucket provisioning tests plus an assertion that no bare directory-name literal survives in the module and ## Scope

- `src/cadrumo/adapters/persistence/storage/bucket/_layout.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Re-point bucket_paths onto the scoped accessor, gated by the existing bucket provisioning tests plus an assertion that no bare directory-name literal survives in the module

## Scope

- `src/cadrumo/adapters/persistence/storage/bucket/_layout.py`

## Description

- Interpret "the scoped accessor" as `storage_location(StorageCategory.X)`
  read directly, following the idiom already established elsewhere in this
  package (`master_key/_master_key.py`, `_rotation.py`) for explicit-root,
  no-IO path composition -- not `bucket_scoped_storage_path`, which resolves
  its root from settings and would have forced a signature change across the
  53+ call sites depending on `bucket_paths`' explicit-root contract.
- Re-point `bucket_paths` to read `storage_location(StorageCategory.BUCKETS
  / BUCKET_DATABASE / BUCKET_BLOBS / BUCKET_AUDIT).relative_path()` instead
  of the four `_namespace_registry`-bridged named constants.
- Confirm byte-identical resolution before and after for every path this
  touches.
- Add a structural AST test to `test_layout.py` confirming no bare
  directory-name literal survives in `_layout.py`, matching the shape of the
  core name-unification gate. Mutation-proven against a synthetic pre-fix
  snippet rather than by mutating the shared production file in place.

## Outcome

`_layout.py` no longer imports from the `_namespace_registry` re-export
bridge at all; every directory-run literal is now a single read of the core
taxonomy. Full bucket, storage, and dependent application suites re-run
clean (1192 + 897 passed across separate runs).

## Notes

None. No skipped work, no scaffolds left in code. Landed together with S21
in commit 64a4e3ab1e.
