---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:f193d7b5825bf8bcc868a59aac3b8af89d732d15a6c774f873e979b0ab903510'
step_id: 'S48'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---

# Restore canonical formatting on the M210 claimed-year design-axis proof introduced by S46, preserving its generalized mutation-bite semantics

## Scope

- `src/cadrumo/domain/calculations/registry/tests/test_layout_design_applies_to_claimed_years.py`

## Description

- Apply the repository-owned Ruff formatter to the generalized M210 claimed-year design-axis proof introduced by S46.
- Preserve selector operands, ordering, M210/M720 classification, presentation-lag behavior, and mutation-bite semantics.
- Re-run the focused M210, M720, and genuine-violation cases and obtain independent review.

## Outcome

The final diff is exactly three additions and one deletion around the nested `selector_start` conditional. Ruff check and format check pass. Five independently selected M210, M720, presentation-lag, and mutation-bite tests pass. Formal review approved with zero findings.

## Notes

The whole claimed-year inventory remains red for thirteen separately owned modelo design gaps. Neither M210 nor M720 appears in that inventory after S46; those unrelated findings do not alter this formatting-only step.
