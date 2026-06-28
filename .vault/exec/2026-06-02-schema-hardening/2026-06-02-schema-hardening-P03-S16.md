---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S16'
related:
  - "[[2026-06-02-registry-hardening-next-work-plan]]"
---




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
