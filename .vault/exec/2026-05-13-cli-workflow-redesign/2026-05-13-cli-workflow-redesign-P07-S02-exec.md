---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'P07.S02'
related:
  - "[[2026-05-13-cli-workflow-redesign-config-repair-shape-plan]]"
---

# `cli-workflow-redesign` P07.S02 — `logging.file` next_action points at the right command

## Finding

C-2 (CRITICAL). The `logging.file` diagnostic row's failure-mode
`next_action` was `"aeat --help"`, which gives the operator a help page
rather than the recovery command. The ADR mapping table mandates
`aeat config repair logs` for this row.

## Resolution

Changed `next_action` on the warn branch of the `logging.file` row in
`src/aeat/application/diagnostics.py` from `"aeat --help"` to
`"aeat config repair logs"`. No test changes were required: the existing
`build_config_repair_report` tests assert the row's presence and status,
not the literal value of its `next_action`; only the ADR mapping pinned
that value, and the implementation now agrees with the ADR.

## Verification

Existing diagnostics tests still pass; the row now closes the recovery
loop the operator expects.
