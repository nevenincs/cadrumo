---
tags:
  - '#exec'
  - '#core-authority'
step_id: S74
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
---

# core-authority W08.P21.S74 - Google adapter cycle edges (STRUCTURAL BLOCK)

## Outcome

STRUCTURAL BLOCK: The 17 bi-directional Google adapter cycle edges (MIGRATE-002)
between `application/storage/calc_sheets/` and `adapters/outbound/google/` cannot be
broken within S74's scope without a larger refactor.

Cycle anatomy:
- `adapters/outbound/google/_calc_sheets_apply.py:43` (normal) imports
  `SheetExportPlan, SheetRowSet, SheetFormulaCell, SheetValueCell, SheetCellConstraint,
  SheetProtectedRange, TabName` from `application.storage.calc_sheets`.
- `adapters/outbound/google/_calc_sheets_pull.py:54-57` (normal) imports from
  `application.storage.calc_sheets.*`.
- `application/storage/calc_sheets/_parity_harness.py:325` (local_scope) imports
  `apply_export_plan` from `adapters.outbound.google._calc_sheets_apply`.

The fix requires moving the shared data records (`SheetExportPlan`, `SheetRowSet`, etc.)
from `application/storage/calc_sheets/_records.py` to a layer that both application and
adapters can import from (either `domain/` or `core/`). These are pure pydantic
records with no adapter-specific dependencies. This is a bounded but non-trivial relocation
affecting the Google adapter's import tree and the calc_sheets engine's imports.

Root cause: `application/storage/calc_sheets/` was designed as a shared vocabulary between
the engine driver and the Google adapter, but placed in application/ where adapters cannot
import from. The records should be in a domain or core module.

REMEDIATION PATH: Extract `_records.py` content to `domain/calculations/registry/_sheet_records.py`
or `core/sheet_records.py`, update all importers (engine, apply adapter, pull adapter,
parity harness). Track as a follow-up Step in W09 or W10.

MIGRATE-002, Rule 2.

## Commit

No code change for S74 (blocked).

## Verification

Not applicable (blocked). The `_parity_harness.py` local_scope import is documented
as a structural block for future resolution.
