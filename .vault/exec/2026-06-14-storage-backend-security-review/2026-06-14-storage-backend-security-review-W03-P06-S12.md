---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-14'
modified: '2026-06-14'
step_id: 'S12'
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
     The S12 and 2026-06-14-storage-backend-security-review-plan placeholders are machine-filled by
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
     The fsync the staged tmp file and the parent directory before and after os.replace on the manifest write and ## Scope

- `src/aeat/adapters/persistence/storage/bucket/_manifest_io.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# fsync the staged tmp file and the parent directory before and after os.replace on the manifest write

## Scope

- `src/aeat/adapters/persistence/storage/bucket/_manifest_io.py`

## Description

- Rewrite `write_manifest` to open the `.tmp` sibling explicitly, `flush` +
  `os.fsync` the fd before `os.replace`, then `fsync_parent_dir(target)` after.

## Outcome

The manifest atomic write is now power-loss durable (matching the rotation
atomic-write path): a hard crash can no longer leave a zero-length manifest that
reads back as ProfileNotFound for a live bucket. 109 bucket tests green.
Committed in `382b5c08e`.

## Notes

None.
