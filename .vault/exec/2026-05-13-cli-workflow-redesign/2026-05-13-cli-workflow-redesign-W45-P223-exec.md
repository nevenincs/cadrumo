---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W45.P223'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-13-cli-workflow-redesign-app-modelo-discard-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-adr]]'
---

# `cli-workflow-redesign` `W45.P223`

De-shim / de-stub phase. The discard state transition is
audit-only — no shim re-activates a discarded unit, no stub
soft-deletes, and no compatibility-mode tolerance for
mis-shaped discard records.

## Description

Three invariants pin the audit-only contract:

1. The cross-field model validator on `WorkUnit` refuses any
   record that claims DRAFT state but carries discard
   metadata, or claims DISCARDED state without the required
   discarded_at + discarded_by fields. There is no "soft" or
   "intermediate" discard state.
2. `discard_work_unit` rejects re-discard with
   `WorkUnitAlreadyDiscardedError`. There is no "discard
   override" or "force discard" flag — the operator must
   accept that a discarded unit is terminal.
3. `rename_work_unit` rejects mutation on a discarded unit
   with `WorkUnitMutationRefusedError`. No metadata field on a
   discarded unit is mutable post-discard; the operator must
   create a fresh work unit to continue on the same modelo /
   year / period.

Three regression tests pin these contracts directly:

- `test_discard_work_unit_raises_when_already_discarded`
- `test_rename_refuses_to_mutate_a_discarded_work_unit`
- `test_work_unit_schema_rejects_discard_metadata_on_draft_state`
- `test_work_unit_schema_requires_discard_metadata_on_discarded_state`

Closed plan rows: `W45.P223.S1333`, `W45.P223.S1334`,
`W45.P223.S1335`, `W45.P223.S1336`, `W45.P223.S1337`,
`W45.P223.S1338`.

## Tests

All four contract-pinning tests pass as part of the 30-test
`src/aeat/domain/modelos/test_work_unit.py` suite.
