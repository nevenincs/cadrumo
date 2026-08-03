---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:718d4faa240b2a07575b505a10090e766bf1756404ea992bbf5aec6d4cf43d4b'
step_id: 'S27'
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
     The S27 and 2026-08-03-canonical-storage-management-plan placeholders are machine-filled by
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
     The Add keystore_sidecar_path validating keystore separation then joining the sidecar filename, and export it from the bucket package facade, gated by a test asserting an unvalidated separation refuses before any path is returned and ## Scope

- `src/cadrumo/adapters/persistence/storage/bucket/_keystore_paths.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add keystore_sidecar_path validating keystore separation then joining the sidecar filename, and export it from the bucket package facade, gated by a test asserting an unvalidated separation refuses before any path is returned

## Scope

- `src/cadrumo/adapters/persistence/storage/bucket/_keystore_paths.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

## Outcome

Landed in `6099f113dd`, confirmed at HEAD. `keystore_sidecar_path(*, storage_root, bucket_id, filename)` in `src/cadrumo/adapters/persistence/storage/bucket/_keystore_paths.py:116-138` calls `validate_keystore_separation` before joining `filename` onto the bucket's keystore directory, and is exported from the bucket package facade (`__all__` at line 141). Gated by `test_sidecar_path_refuses_before_returning_when_separation_invalid` in `bucket/tests/test_keystore_paths.py:87` (positive control) alongside `test_sidecar_path_joins_filename_onto_keystore_directory` at line 82.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->
