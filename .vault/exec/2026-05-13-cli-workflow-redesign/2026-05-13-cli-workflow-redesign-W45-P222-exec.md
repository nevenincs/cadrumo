---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W45.P222'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-13-cli-workflow-redesign-app-modelo-discard-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-adr]]'
---

# `cli-workflow-redesign` `W45.P222`

Shadow-duplicate removal phase. The pre-existing
`test_no_parallel_work_unit_model_outside_canonical_module` and
`test_no_parallel_work_unit_storage_namespace` boundary tests
extend transparently to the new state machinery — the discard
metadata fields live on the same canonical `WorkUnit` record at
the same canonical storage namespace.

## Description

No new module is introduced; the discard verb shares the
existing canonical surfaces:

- `WorkUnit` schema (`aeat.domain.modelos._work_unit`) — only
  declaration of the record type.
- `WorkUnitCatalogueRepository` (`aeat.domain.modelos._repository`)
  — only writer to the `aeat.domain.modelos.work_units`
  namespace.
- `aeat.application.modelo._actions` — only call site for the
  WorkUnit-mutating helpers (`create / discard / rename`).

The wave introduces no parallel state machinery; the existing
"no parallel WorkUnit class" and "no parallel storage namespace"
boundary guards in `test_work_unit.py` continue to fire against
the same set of paths.

Closed plan rows: `W45.P222.S1327`, `W45.P222.S1328`,
`W45.P222.S1329`, `W45.P222.S1330`, `W45.P222.S1331`,
`W45.P222.S1332`.

## Tests

Existing boundary tests pass alongside the 9 new W45 tests in
`src/aeat/domain/modelos/test_work_unit.py`.
