---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-05'
modified: '2026-07-17'
body_hash: 'sha256:8c79a05d9ac89695c707924c832e56dd0fa2098cbeb121d0bffcf0b2c265b67d'
step_id: 'S216'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Rewire 3 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.user_profile`

## Scope

- `src/aeat/domain/calculations/registry/_validate.py`
## Description

- Reconcile $display as an individual exec record for a W02 production consumer-rewrite row already checked in the plan.
- Preserve the row intent: Rewire 3 cross-package private import name(s) in this file onto the promoted facade(s) of `aeat.domain.user_profile`.
- Tie this row to the application/domain calculations rewrite batch recorded by `W02.P43.S199` and landed in `bd7d5abdb`.
- Record no new implementation work; this document splits already-landed batched evidence into the required one-record-per-step shape.

## Outcome

The checked row now has its own exec record. The matching anchor evidence for $anchor recorded codemod dry-run/apply, a public parsing-alias rewrite, import sorting and formatting, and clean `pytest --collect-only -q src/aeat` for the 17-file batch. After the bulk scaffold pass, plan status reports xec_missing_ids is empty.

## Notes

Evidence-only reconciliation. The codebase has continued to evolve after the original W02 landing, so this record cites the historical landed evidence and does not claim a fresh source edit.
