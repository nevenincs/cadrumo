---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W45.P224'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-13-cli-workflow-redesign-app-modelo-discard-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-adr]]'
---

# `cli-workflow-redesign` `W45.P224`

Real-behaviour verification. Nine new tests drive the discard
state machinery against the same in-memory fake repository the
W38 lifecycle tests use.

## Description

W45 test additions (in
`src/aeat/domain/modelos/test_work_unit.py`):

- `test_discard_work_unit_transitions_to_discarded_state` —
  asserts `state` flips to `DISCARDED`, audit metadata is
  captured, `updated_at` bumps to the discard timestamp.
- `test_discard_work_unit_accepts_omitted_reason` — `--reason`
  is optional; `discard_reason` stays `None`.
- `test_discard_work_unit_raises_on_missing_id` — typed
  `WorkUnitNotFoundError` on absent id.
- `test_discard_work_unit_raises_when_already_discarded` — typed
  `WorkUnitAlreadyDiscardedError` on retry; audit trail stays
  clean.
- `test_rename_refuses_to_mutate_a_discarded_work_unit` —
  typed `WorkUnitMutationRefusedError` on rename-after-discard.
- `test_list_work_units_excludes_discarded_by_default` — pins
  the default-listing contract.
- `test_list_work_units_includes_discarded_when_flag_set` — pins
  the `include_discarded=True` listing contract.
- `test_work_unit_schema_rejects_discard_metadata_on_draft_state`
  — DRAFT records must not carry discard metadata.
- `test_work_unit_schema_requires_discard_metadata_on_discarded_state`
  — DISCARDED records must carry both `discarded_at` and
  `discarded_by`.

Closed plan rows: `W45.P224.S1339`, `W45.P224.S1340`,
`W45.P224.S1341`, `W45.P224.S1342`, `W45.P224.S1343`,
`W45.P224.S1344`.

## Tests

`uv run --no-sync pytest src/aeat/domain/modelos/test_work_unit.py
-q` — 30 / 30 pass.
