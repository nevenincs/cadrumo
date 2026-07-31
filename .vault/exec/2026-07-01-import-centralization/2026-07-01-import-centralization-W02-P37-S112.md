---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-05'
modified: '2026-07-17'
body_hash: 'sha256:156491411095fdd9a7d706111f24f3c7196aa26d20c3feddb6f5e3c8c6a6111e'
step_id: 'S112'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Rewire 5 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.persistence.storage.crypto`

## Scope

- `src/aeat/adapters/persistence/storage/master_key/_recovery.py`
## Description

- Reconcile $display as an individual exec record for a W02 production consumer-rewrite row already checked in the plan.
- Preserve the row intent: Rewire 5 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.adapters.persistence.storage.crypto`.
- Tie this row to the adapters production rewrite batch recorded by `W02.P37.S97` and landed in `85c3b2ad6`.
- Record no new implementation work; this document splits already-landed batched evidence into the required one-record-per-step shape.

## Outcome

The checked row now has its own exec record. The matching anchor evidence for $anchor recorded codemod dry-run/apply, import sorting and formatting, and clean `pytest --collect-only -q src/aeat` for the 50-file batch. After the bulk scaffold pass, plan status reports xec_missing_ids is empty.

## Notes

Evidence-only reconciliation. The codebase has continued to evolve after the original W02 landing, so this record cites the historical landed evidence and does not claim a fresh source edit.
