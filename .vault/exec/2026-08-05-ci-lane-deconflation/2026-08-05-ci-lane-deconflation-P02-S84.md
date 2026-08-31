---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:8b9d821ef1c10d7c385253e92ddd70d40da212fab7ea1dcb4da9294e51f6d778'
step_id: 'S84'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Propose a grounded decomposition for registry/record_design.py.

## Scope

- `src/cadrumo/domain/calculations/registry/record_design.py`
- `dev/audit/size_budget_baseline.json`

## Changes

- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P02-S84.md`
- `A` `.vault/audit/2026-08-31-ci-lane-deconflation-p02-s84-execution-self-review-audit.md`

## Notes

- Historical read-only proposal only: four name-based groups (PDF, row repair, workbook/XLS, corrections) were measured, but the projected remainder still exceeded budget. No extraction, baseline write, or current measurement is claimed.
- S85 corrected the grouping and added visual handling; S89 later refuted the mechanical five-way split after proving bidirectional dependencies. This record preserves the original proposal as superseded analysis, not a current implementation instruction.
- `record_design.py` has peer worktree changes, so no present-tense size claim is made.
