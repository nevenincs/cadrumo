---
tags:
  - '#exec'
  - '#docs-terminology-search'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S06'
related:
  - "[[2026-07-13-docs-terminology-search-plan]]"
---

# Prove per-kind parity: preprocess run-one output text equals the committed sidecar text for a representative source of each kind, asserted by a committed test

## Scope

- `dev/docs/preprocess/tests/`

## Description

- Add `test_hook_units_are_parity_with_committed_sidecars`, parametrised per
  source kind, asserting hook unit texts equal committed sidecar unit texts
  for the smallest representative of each kind.
- Run the real upstream runner end to end per kind.

## Outcome

7/7 hook gates green (`485ac85614`). Live `preprocess run-one` evidence:
HTML representative preprocessed with 2 sections, PDF (calendario
contribuyente 2025) with 82, Diseños workbook (modelo 036) with 13.

## Notes

The atomic cutover (S07) stays open: resolver retarget, sidecar deletion,
docstring correction, and the equal-or-superset sweep proof land together.
