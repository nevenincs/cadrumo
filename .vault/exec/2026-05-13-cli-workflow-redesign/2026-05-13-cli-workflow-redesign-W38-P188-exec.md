---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W38.P188'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-modelo-work-units-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-adr]]'
---

# `cli-workflow-redesign` `W38.P188`

De-shim / de-stub phase. The work-unit concept is greenfield —
there are no pre-existing stub records, no compatibility shims,
and no rejected work-unit shapes to drop. The content-addressing
invariant on `WorkUnit` is the forward guard.

## Description

The W38 deliverable does not migrate any legacy work-unit record.
The closest existing concepts (filing drafts, draft revisions)
remain in their own domains under `aeat.domain.filing`; they are
not folded into the work-unit catalogue.

The content-addressing invariant on `WorkUnit` (model validator
in `_work_unit.py`) is the forward guard: a persisted record
whose stored `work_unit_id` disagrees with the deterministic
derivation is refused on read. This prevents a future agent from
manually editing the on-disk catalogue to attach a custom id to a
work unit; any such drift becomes an immediate validation error
rather than silent storage corruption.

Closed plan rows: `W38.P188.S1123`, `W38.P188.S1124`,
`W38.P188.S1125`, `W38.P188.S1126`, `W38.P188.S1127`,
`W38.P188.S1128`.

## Tests

`test_work_unit_rejects_id_that_does_not_match_derivation` in
`src/aeat/domain/modelos/test_work_unit.py` is the regression
guard.
