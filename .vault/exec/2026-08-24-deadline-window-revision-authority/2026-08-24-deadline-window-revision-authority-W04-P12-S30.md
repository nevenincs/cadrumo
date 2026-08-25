---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:862b3498d201e9219ca1e542c7e03402cb798a7be42f6ad968291fe9af1aa528'
step_id: 'S30'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---
# Add overview and workflow regressions comparing ordered semantic coordinates without multiplicity-erasing assertions

## Scope

- `src/cadrumo/application/overview/tests/`
- `src/cadrumo/application/workflow/tests/`

## Description

- Discover canonical overview and workflow schedule projections with `vaultspec-rag` before editing.
- Replace the workflow parity regression's set projections with ordered semantic-coordinate tuples.
- Add a real-registry overview regression proving Modelo 303 filing year 2025 projects exactly `1T`, `2T`, `3T`, and `4T`, once each and in canonical order.
- Retain the fail-closed workflow-target regression for duplicate canonical schedule rows.
- Run focused overview and workflow tests and Ruff over both changed test modules.

## Outcome

The overview and workflow consumer witnesses now preserve sequence and multiplicity. A duplicate, omitted, or reordered obligation changes the asserted tuple and fails instead of being erased by set construction. The real overview projection proves the operator-visible Modelo 303 2025 calendar contains exactly four quarterly obligations.

## Notes

Focused verification passed: two overview tests, two workflow tests, and Ruff. The plan scope labels the second surface as `application/modelo/tests`; the canonical workflow deadline consumer and its existing regression live under `application/workflow/tests`, so the implementation followed the actual owner discovered by RAG.
