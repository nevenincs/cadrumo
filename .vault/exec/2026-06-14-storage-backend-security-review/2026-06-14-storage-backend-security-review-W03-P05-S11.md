---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-14'
modified: '2026-06-14'
step_id: 'S11'
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
     The S11 and 2026-06-14-storage-backend-security-review-plan placeholders are machine-filled by
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
     The Add a concurrent-writer regression proving two sessions on one bucket do not raise an immediate database-locked error and ## Scope

- `src/aeat/adapters/persistence/storage/sql/tests/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add a concurrent-writer regression proving two sessions on one bucket do not raise an immediate database-locked error

## Scope

- `src/aeat/adapters/persistence/storage/sql/tests/`

## Description

- Add `test_concurrent_writers_do_not_raise_database_locked`: four threads, each
  with its own engine over one bucket DB, run 25 inserts apiece behind a barrier;
  assert no writer raised and all 100 rows landed.
- Add `test_engine_applies_concurrency_pragmas` asserting busy_timeout=5000 and
  foreign_keys=1.

## Outcome

Real-behavior concurrency regression green. Per-thread engines guarantee each
SQLite connection is created and used in its owning thread. Committed in `47f95f61e`.

## Notes

The earlier discovery that WAL breaks ~21 at-rest raw-db readers is what drove the
busy_timeout-only scope; see S33.
