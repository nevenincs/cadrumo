---
tags:
  - '#exec'
  - '#canonical-storage-management'
date: '2026-08-03'
modified: '2026-08-03'
body_schema: 'body-v1'
body_hash: 'sha256:27c08ff43d078c1a815053c68c65f87d96e3284b6b0a6eda084d692f6b3e8bee'
step_id: 'S21'
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
     The S21 and 2026-08-03-canonical-storage-management-plan placeholders are machine-filled by
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
     The Re-point keystore_path onto the scoped accessor while preserving the keystore-separation validation, gated by the existing separation-refusal test and ## Scope

- `src/cadrumo/adapters/persistence/storage/bucket/_keystore_paths.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Re-point keystore_path onto the scoped accessor while preserving the keystore-separation validation, gated by the existing separation-refusal test

## Scope

- `src/cadrumo/adapters/persistence/storage/bucket/_keystore_paths.py`

## Description

- Establish the real keystore layout from `validate_keystore_separation`'s
  own refusal logic before touching anything: `<root>/keystore/<bucket_id>/`,
  sibling to `<root>/buckets/`, deliberately not read off the taxonomy
  declaration or a test. Confirmed `storage_location(StorageCategory.
  BUCKET_KEYSTORE).relative_path()` resolves to exactly that shape (`root /
  "keystore" / bucket_id`) via direct computation, matching what
  `KEYSTORE_DIRNAME` already resolved to.
- Re-point `keystore_root` to read `storage_location(StorageCategory.
  BUCKET_KEYSTORE).relative_path()` instead of the `_namespace_registry`
  -bridged `KEYSTORE_DIRNAME`.
- Re-point `validate_keystore_separation`'s `buckets_parent` to
  `paths.bucket_dir.parent` -- the already-resolved `bucket_paths()` result
  -- instead of a second read of the governed "buckets" name, removing a
  duplicate rather than adding one.
- Leave the separation-refusal logic itself (the `_is_under` checks against
  `paths.db_dir` and `buckets_parent`) completely untouched.

## Outcome

Confirmed byte-identical resolution for `keystore_root`, `keystore_path`,
and that `validate_keystore_separation` still refuses a keystore configured
under the bucket db dir. Full bucket, storage, and dependent application
suites re-run clean (1192 + 897 passed across separate runs).

## Notes

None. No skipped work, no scaffolds left in code. Landed together with S20
in commit 64a4e3ab1e.
