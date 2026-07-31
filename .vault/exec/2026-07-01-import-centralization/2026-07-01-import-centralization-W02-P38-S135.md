---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-05'
modified: '2026-07-17'
body_hash: 'sha256:7f20e668860331ea764d436ff26abfb5de173dedb53f4034b435ce303155c174'
step_id: 'S135'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.renta`

## Scope

- `src/aeat/entrypoints/cli/_modelo_maritime_cli.py`
## Description

- Reconcile $display as an individual exec record for a W02 production consumer-rewrite row already checked in the plan.
- Preserve the row intent: Rewire 1 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.renta`.
- Tie this row to the `aeat.entrypoints.cli` production rewrite batch recorded by `W02.P38.S120` and landed in `b86255941`.
- Record no new implementation work; this document splits already-landed batched evidence into the required one-record-per-step shape.

## Outcome

The checked row now has its own exec record. The matching anchor evidence for $anchor recorded codemod dry-run/apply, import sorting and formatting, and clean `pytest --collect-only -q src/aeat` for the 20-file batch. After the bulk scaffold pass, plan status reports xec_missing_ids is empty.

## Notes

Evidence-only reconciliation. The codebase has continued to evolve after the original W02 landing, so this record cites the historical landed evidence and does not claim a fresh source edit.
