---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W45.P221'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-13-cli-workflow-redesign-app-modelo-discard-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-adr]]'
---

# `cli-workflow-redesign` `W45.P221`

Backend wiring for the modelo work-unit discard verb. Extends
the `WorkUnit` record with a `state` enum and discard audit
metadata; adds `discard_work_unit` application action; refuses
mutation on discarded units.

- Modified: `src/aeat/domain/modelos/_work_unit.py`
- Modified: `src/aeat/application/modelo/_actions.py`
- Modified: `src/aeat/application/modelo/__init__.py`
- Modified: `src/aeat/core/errors/registry/_domain.py`

## Description

Domain additions:

- `WorkUnitState` (StrEnum): `DRAFT`, `DISCARDED`.
- `WorkUnit.state` (default `DRAFT`), `WorkUnit.discarded_at`,
  `WorkUnit.discarded_by`, `WorkUnit.discard_reason` — all
  Optional with `None` default so existing persisted records
  load forward-compatibly.
- Cross-field model validator: `DRAFT` units must not carry
  discard metadata; `DISCARDED` units must carry both
  `discarded_at` and `discarded_by`; `discarded_at` must not
  precede `created_at`.

Application additions:

- `discard_work_unit(work_unit_id, *, actor, reason=None,
  clock=None)` — transitions the unit to DISCARDED, captures
  audit metadata, bumps `updated_at`.
- `WorkUnitAlreadyDiscardedError` — raised on re-discard
  attempts (idempotent retries would corrupt audit history).
- `WorkUnitMutationRefusedError` — raised when `rename_work_unit`
  targets a discarded unit.
- `list_work_units` gains `include_discarded` (default `False`);
  discarded units are excluded from the default view.

Error registry: two new codes
(`ERROR_MODELO_WORK_UNIT_ALREADY_DISCARDED` and
`ERROR_MODELO_WORK_UNIT_MUTATION_REFUSED`), each carrying a
default suggestion that points the operator at the corrective
verb.

Closed plan rows: `W45.P221.S1321`, `W45.P221.S1322`,
`W45.P221.S1323`, `W45.P221.S1324`, `W45.P221.S1325`,
`W45.P221.S1326`.

## Tests

`uv run --no-sync pytest src/aeat/domain/modelos/test_work_unit.py
-q` — 30 / 30 pass.
