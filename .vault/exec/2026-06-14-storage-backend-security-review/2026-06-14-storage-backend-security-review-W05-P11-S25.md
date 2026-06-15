---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S25'
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
     The S25 and 2026-06-14-storage-backend-security-review-plan placeholders are machine-filled by
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
     The Promote the sealed-archive read and write helpers to the bucket package all and rebind the maintenance service call sites and ## Scope

- `src/aeat/adapters/persistence/storage/bucket/__init__.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Promote the sealed-archive read and write helpers to the bucket package all and rebind the maintenance service call sites

## Scope

- `src/aeat/adapters/persistence/storage/bucket/__init__.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

- Promote `write_sealed_archive`, `read_sealed_archive`, and `SealedArchiveContents` to the bucket package `__all__` (eager re-export; the sealed-archive modules import only stdlib plus the already-imported `_export_header`, so the surface stays import-light).
- Rebind the `BucketMaintenanceService` export call site to import `write_sealed_archive` through the package surface (folded into the existing `from ...storage.bucket import ...` block) instead of the private `bucket._sealed_archive_writer` submodule.
- Rebind the service import call site to `from ...storage.bucket import read_sealed_archive` instead of the private `bucket._sealed_archive_reader` submodule.
- Rebind the application-layer test (`test_service_import_export`) to the package surface. Adapter-internal tests keep their intra-package sibling imports.

## Outcome

Closes the `service-imports-via-top-level-reexports` violation for the sealed-archive helpers: the application-layer `BucketMaintenanceService` no longer dots into the bucket package's private submodules. Lint clean; the sealed-archive roundtrip suite, the service import/export suite, and both `user_profile` lazy-boundary gates plus the CLI lazy-command-tree gate pass (18 passed). Committed as `refactor(bucket-adapter): promote sealed-archive read/write helpers to bucket package surface (S25)`.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

None. The promoted symbols carry no extra eager-import weight, so json-pipe-safety is unaffected (lazy-boundary gates green).
