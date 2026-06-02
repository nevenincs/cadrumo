---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-06-02'
step_id: 'S165'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cross-domain-continuity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.
     step_id is the originating Step's canonical identifier, e.g. S01.

     Related: use wiki-links as '[[YYYY-MM-DD-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add frontmatter fields
     outside the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path. -->

# merge active_bucket_id_or_raise and require_active_bucket_id into one canonical function update all call sites

## Scope

- `src/aeat/application/workflow/_models.py`

## Description

Consolidated `active_bucket_id_or_raise` and
`require_active_bucket_id` into a single canonical function in
`src/aeat/application/workflow/_models.py`. The two functions had
literally identical bodies; their docstrings carried different
audience notes which are merged into the canonical
`require_active_bucket_id` docstring.

Deleted `active_bucket_id_or_raise`; promoted
`require_active_bucket_id` to the package surface
(`application.workflow.__init__` re-export + __all__ entry).

Migrated 6 consumer files
(`application/review/_operator.py`,
`entrypoints/cli/_app_live.py`, `_common.py`, `_ledger.py`,
`_modelo.py`, and `test_ledger_exception_propagation.py`) from
the deleted alias to the canonical via a bulk-text rewrite.

## Outcome

15 workflow tests
(`test_active_profile_resolution.py` 4 + `test_models.py` 11) pass
after the consolidation. Import surface verified:
`from aeat.application.workflow import require_active_bucket_id`
resolves to the same function as the direct `_models` import.

## Notes

Real refactor. No shim re-export of the deleted name (per the
no-shims rule). Wave-1 drift sweep DUPLICATE finding closed.
