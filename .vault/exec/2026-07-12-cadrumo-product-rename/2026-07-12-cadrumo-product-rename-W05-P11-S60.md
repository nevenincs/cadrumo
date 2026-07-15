---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S60'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Update release-readiness project-name parsing and real behavior tests

## Scope

- `dev/release`

## Description

- Parse the root and both companion project names from their real `pyproject.toml` files.
- Compare those names with the single canonical `PRODUCT_IDENTITY` distribution tuple.
- Add a blocking release-readiness result for any root or companion name drift.
- Prove every former distribution name is rejected through real temporary project files.

## Outcome

Release readiness now blocks unless the project tuple is exactly `cadrumo`,
`cadrumo-data-manuals`, and `cadrumo-data-official`. The real repository gate
reports all blocking checks clean; Ruff and all twenty-one focused tests pass.

## Notes

No compatibility alias or fallback is accepted. AEAT remains untouched where
it denotes the Spanish tax authority; this check is limited to product
distribution metadata.

The S60 plan checkbox landed concurrently with the adjacent CI-workflow step,
so the final S60 commit does not duplicate that already-closed plan byte.
