---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-14'
modified: '2026-06-14'
step_id: 'S13'
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
     The S13 and 2026-06-14-storage-backend-security-review-plan placeholders are machine-filled by
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
     The Re-read and re-validate the holder PID immediately before the stale-lock reclaim unlink and ## Scope

- `src/aeat/adapters/persistence/storage/bucket/_lockfile.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Re-read and re-validate the holder PID immediately before the stale-lock reclaim unlink

## Scope

- `src/aeat/adapters/persistence/storage/bucket/_lockfile.py`

## Description

- Add a re-read guard in `_reclaim_if_stale`: after judging the holder PID dead,
  re-read it immediately before the unlink and reclaim only when the record is
  byte-identical, so a peer's freshly re-created live lock is never deleted.

## Outcome

The stale-reclaim TOCTOU window is closed for the common case. 109 bucket tests
green. Committed in `382b5c08e`.

## Notes

A fully race-free reclaim needs inode-level operations (platform-specific); the
re-read guard is the proportionate fix the finding recommended for a MEDIUM item,
and the lock does not gate row writes so residual exposure is bounded. No
deterministic regression test added because the race is not reproducible without
internal injection (which the quality-gates rule discourages); existing lockfile
concurrency tests confirm no regression.
