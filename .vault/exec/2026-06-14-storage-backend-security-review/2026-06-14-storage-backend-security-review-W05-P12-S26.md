---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-14'
modified: '2026-06-14'
step_id: 'S26'
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
     The S26 and 2026-06-14-storage-backend-security-review-plan placeholders are machine-filled by
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
     The Replace the three private secure-objects-for-bucket route helpers with the canonical secure_object_repository_for_bucket wrapper and ## Scope

- `src/aeat/domain/invoices/_repository.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Replace the three private secure-objects-for-bucket route helpers with the canonical secure_object_repository_for_bucket wrapper

## Scope

- `src/aeat/domain/invoices/_repository.py`

## Description

- Promote `secure_object_repository_for_bucket` to the storage package `__all__`.
- Replace the three private `_secure_objects_for_bucket` helpers (invoices,
  transactions, user_profile) that re-derived the route via
  `inspect_bucket_storage_runtime(...).secure_object_repository()` with delegation
  to the canonical `secure_object_repository_for_bucket`.

## Outcome

Route policy now lives in one place; a future readiness/route change reaches all
three consumers. No data-exposure change (same substrate). 146 tests + smoke green.
Committed in `c22f87dbc`.

## Notes

The Axis-1 audit flagged this as enrollment-consistency (MEDIUM), explicitly not a
data-exposure bug; confirmed.
