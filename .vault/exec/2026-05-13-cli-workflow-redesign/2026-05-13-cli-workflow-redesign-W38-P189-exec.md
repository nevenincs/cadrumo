---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W38.P189'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-modelo-work-units-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-adr]]'
---

# `cli-workflow-redesign` `W38.P189`

Real-behaviour verification. Twenty-one tests drive the work-unit
domain + application surfaces end-to-end through a purely
in-memory fake repository injected at the action layer.

## Description

Suite breakdown
(`src/aeat/domain/modelos/test_work_unit.py`):

- `derive_work_unit_id` (4 tests): 64-char lowercase hex shape;
  determinism; bucket-scoping; case normalisation on modelo +
  period.
- `WorkUnit` schema (3 tests): strict / frozen / extras-forbid;
  content-addressing rejection; `updated_at` ≥ `created_at`
  temporal invariant.
- `WorkUnitCatalogue` schema (3 tests): key-record alignment;
  duplicate-id rejection in `from_work_units`; pure-helper
  invariants for `upsert_work_unit` / `remove_work_unit`.
- Application `create_work_unit` (3 tests): idempotent on the
  four-axis key (second call returns the same record without
  re-persisting); default name shape `<modelo>-<year>-<period>`;
  explicit name honoured.
- Application `list_work_units` (2 tests): sorted by
  `(bucket_id, filing_year, modelo, period)`; bucket filter.
- Application `get_work_unit` (1 test): `WorkUnitNotFoundError`
  on missing id.
- Application `rename_work_unit` (2 tests): preserves
  `work_unit_id`, bumps `updated_at`; raises on missing id.
- Boundary regression guards (2 tests): no parallel `WorkUnit`
  class outside the canonical module; no parallel work-unit
  storage namespace.

The tests inject an in-memory fake repository (matching the
`WorkUnitCatalogueRepository` contract) so the action layer is
exercised without a SQL backend. The fake also counts `save`
calls; the idempotent-create test asserts the second call did
not trigger a persistence write.

Closed plan rows: `W38.P189.S1129`, `W38.P189.S1130`,
`W38.P189.S1131`, `W38.P189.S1132`, `W38.P189.S1133`,
`W38.P189.S1134`.

## Tests

`uv run --no-sync pytest src/aeat/domain/modelos/test_work_unit.py
-q` — 21 / 21 pass.
