---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-07-04'
modified: '2026-07-08'
step_id: 'S09'
related:
  - "[[2026-05-14-cli-workflow-redesign-modelo-145-reopen-plan]]"
---

# Add non-filing communication validation rules for rejected filing, deadline, live-read, and portal surfaces

## Scope

- `src/aeat/domain/calculations/registry`

## Description

- Reconcile the missing per-step exec record for checked row `P02.S09`.
- Use the existing aggregate evidence record `2026-05-14-cli-workflow-redesign-modelo-145-reopen-p02-s07-s10-exec.md` as the implementation authority.
- Confirm the aggregate record covers the non-filing communication validator rules that reject filing, deadline, live-read, portal, and filing-schedule surfaces for Modelo 145.

## Outcome

- No new source work was performed in this reconciliation pass.
- `P02.S09` now has a dedicated per-step exec record, satisfying the plan-closure record-shape requirement while preserving the original aggregate evidence.
- The original aggregate record reports green registry-schema, source-catalogue, ruff, and type-check verification for the P02 communication vocabulary landing.

## Notes

- This record exists to clear a `vault plan status` missing-exec alert for a row already checked before per-step records were enforced.
