---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W38.P186'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-modelo-work-units-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-adr]]'
---

# `cli-workflow-redesign` `W38.P186`

Backend implementation for the modelo work-unit concept.

- Created: `src/aeat/domain/modelos/_work_unit.py`
- Created: `src/aeat/domain/modelos/_repository.py`
- Created: `src/aeat/application/modelo/__init__.py`
- Created: `src/aeat/application/modelo/_actions.py`
- Modified: `src/aeat/core/errors/registry/_domain.py`

## Description

Domain surface (`aeat.domain.modelos`):

- `WorkUnit` (Pydantic v2 strict / frozen / extras-forbid) carries
  `work_unit_id`, `bucket_id`, `modelo` (ModeloCode), `filing_year`,
  `period`, `revision_id`, `name`, `created_at`, `updated_at`.
- `WorkUnitCatalogue` — frozen mapping keyed by `work_unit_id`
  with a model validator that enforces key-record alignment.
- `derive_work_unit_id(bucket_id, modelo, filing_year, period,
  revision_id)` returns the deterministic 64-char lowercase SHA-
  256 hex digest. Inputs are normalised (stripped, modelo + period
  uppercased) before hashing. A model validator on `WorkUnit`
  refuses any persisted record whose stored id disagrees with the
  derivation.
- `WorkUnitCatalogueRepository` reads / writes the catalogue via
  the encrypted `SecureObjectRepository` backend at FINANCIAL
  sensitivity, under the namespace
  `aeat.domain.modelos.work_units`. Helpers `upsert_work_unit`
  and `remove_work_unit` are pure: they return new catalogues
  without mutating the input.

Application surface (`aeat.application.modelo`):

- `create_work_unit(...)` — idempotent on the four-axis key.
  Calling twice with the same key returns the existing record
  without persisting a duplicate.
- `list_work_units(bucket_id=None)` — sorted by
  `(bucket_id, filing_year, modelo, period)`.
- `get_work_unit(work_unit_id)` — raises
  `WorkUnitNotFoundError(ModeloError, KeyError)` when absent.
- `rename_work_unit(work_unit_id, new_name)` — preserves
  `work_unit_id`, bumps `updated_at`.

Error registry: `WorkUnitPersistenceError` registered with code
`FAIL_MODELO_WORK_UNIT_PERSISTENCE`;
`WorkUnitNotFoundError` registered with code
`ERROR_MODELO_WORK_UNIT_NOT_FOUND` and default suggestion
`aeat app modelo work list`.

Closed plan rows: `W38.P186.S1111`, `W38.P186.S1112`,
`W38.P186.S1113`, `W38.P186.S1114`, `W38.P186.S1115`,
`W38.P186.S1116`.

## Tests

`uv run --no-sync pytest src/aeat/domain/modelos/test_work_unit.py
-q` — 21 / 21 pass.
