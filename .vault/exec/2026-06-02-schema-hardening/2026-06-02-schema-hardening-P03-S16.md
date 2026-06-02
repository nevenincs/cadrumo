---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-06-02'
step_id: 'S16'
related:
  - "[[2026-06-02-registry-hardening-next-work-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace schema-hardening with a kebab-case feature tag, e.g. #foo-bar.
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

# Verify M349 base intracomunitaria role coverage

## Scope

- `src/aeat/domain/calculations/registry/test_modelo_349_registry.py`

## Description

- Inspect current M349 registry and test-file state before editing.
- Load Modelo 349 through the production registry loader and enumerate
  `base_intracomunitaria` casillas.
- Add a real-registry regression test for complete
  `base_intracomunitaria` coverage, data type, and legal-reference surface.
- Apply the minimal Ruff import-sort repair required by the touched test file.
- Leave unrelated shared-worktree Modelo 151 WIP untouched.

## Outcome

- Modelo 349 revision `2020-y-siguientes` exposes exactly three
  `base_intracomunitaria` casillas: `op.base-imponible`,
  `rect.base-rectificada`, and `rect.base-anterior`.
- The new regression test asserts all three are `money` casillas and share the
  committed legal-reference tuple.
- The focused M349 test, Ruff check, plan check, and vault body/frontmatter
  checks passed.
- `P03.S16` is complete.

## Notes

- `src/aeat/domain/calculations/registry/test_modelo_349_registry.py` already
  had formatting-only shared-worktree churn before this slice. The staged diff
  must be reviewed explicitly so the new test and import-sort repair remain
  distinguishable from that pre-existing formatting change.
