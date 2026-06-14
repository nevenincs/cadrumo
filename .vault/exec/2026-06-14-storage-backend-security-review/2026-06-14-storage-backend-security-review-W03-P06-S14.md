---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-14'
modified: '2026-06-14'
step_id: 'S14'
related:
  - "[[2026-06-14-storage-backend-security-review-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace storage-backend-security-review with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S14 and 2026-06-14-storage-backend-security-review-plan placeholders are machine-filled by
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
     The Dispose the cached engine when a bucket DB is hard-deleted so a recreated file does not reuse stale connections and ## Scope

- `src/aeat/adapters/persistence/storage/sql/engine.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Dispose the cached engine when a bucket DB is hard-deleted so a recreated file does not reuse stale connections

## Scope

- `src/aeat/adapters/persistence/storage/sql/engine.py`

## Description

- Dispose the cached SQLAlchemy engine pool (then `gc.collect`) at the start of
  `remove_profile_bucket_directory`, before the crash-safe rename.

## Outcome

The bucket's SQLite file handle is released before removal, so the Windows
rename-refusal fallback is avoided and a cached engine can no longer serve stale
connections to a deleted-then-recreated bucket DB. Engines re-create lazily, so
the broad dispose is safe. 134 profile/delete tests green. Committed in `82b8a48f0`.

## Notes

Disposes all cached engines rather than resolving the single per-bucket URL: the
broad dispose is safe (lazy re-create) and guarantees the target handle is freed
cross-platform without the risk of a wrong URL-specific lookup.
