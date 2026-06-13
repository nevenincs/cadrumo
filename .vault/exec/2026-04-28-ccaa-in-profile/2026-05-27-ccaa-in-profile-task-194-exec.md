---
title: "Task #194 — causante_ccaa axis + foral guard"
date: 2026-05-27
modified: '2026-05-27'
tags:
  - "#exec"
  - "#ccaa-in-profile"
step_id: "TASK-194"
commit: "24132efb9"
related:
  - "[[2026-04-28-ccaa-in-profile-summary-exec]]"
---

## Summary

Added `causante_ccaa: CCAA | None` axis to WorkUnit and wired it through the
full CLI → application → domain chain for ISD (M650/M660) and ITPyAJD
(M600/M620) modelos.

## Changes delivered

- **`_work_unit.py`** — `causante_ccaa: CCAA | None = None` field; not part of
  the content-addressing SHA-256 key so the same declaración can be updated
  without creating a new work unit.

- **`_actions.py`** — `create_work_unit` accepts `causante_ccaa: CCAA | None`
  and passes it to the WorkUnit constructor. Import order fixed (period before
  profile._ccaa).

- **`_modelo.py`** — `work_create` exposes `--causante-ccaa` Typer option.
  Foral guard runs after `_validate_filing_year` but before `_guard_stub_modelo`
  so the operator receives `ForalRegimeError` (domain-correct, cites Concierto
  Económico / Ley 12/2002 / Convenio / Ley 28/1990) rather than a generic stub
  refusal when both conditions apply.  The `command_error_boundary` decorator
  surfaces `ForalRegimeError` (AeatError subclass) automatically.

- **`_modelo_payloads.py`** — `WorkUnitPayload.causante_ccaa: str | None`.

- **`es.yml`** — `causante_ccaa_help` locale key under `cli.app.modelo.work`
  citing Ley 22/2009 Art. 32 for Hacienda competente routing.

- **`test_work_unit.py`** — 3 new tests (roundtrip, identity, default-none).
  Fixed 14 pre-existing failures: M303 period `Q1`→`1T`, revision `"rev"`→
  `"2009-y-siguientes"`; M130 revision→`"2019-y-siguientes"`.  Fixed
  `test_no_parallel_work_unit_storage_namespace` to exclude
  `_namespace_registry.py` (legitimate namespace declaration table, not a
  shadow store).

- **`test_modelo_650_stub_refusal.py`** — 2 additional CLI foral guard tests
  (`--causante-ccaa pais_vasco` and `--causante-ccaa navarra`) confirming foral
  guard fires before stub guard.

## Quality gates

- 38/38 tests pass (`test_work_unit.py` + `test_modelo_650_stub_refusal.py`)
- ruff: all checks passed on all modified files
- pyright: 0 new errors (pre-existing `reportAttributeAccessIssue` on
  `_modelo.py:2153` unrelated to this task)
