---
step_id: S326
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-30'
modified: '2026-05-30'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W03.P14.S326 — migrate 5 importers to aeat.core.aggregation

## Outcome

Migrated all 5 production importers of `AggregationSourceKind` from the old `_source_kinds` module to `aeat.core.aggregation`. Deleted `src/aeat/application/aggregation/_source_kinds.py` (file contained only `AggregationSourceKind`; no other symbols).

## Importers migrated

- `src/aeat/application/aggregation/_counterpart.py` — `from ._source_kinds import` → `from aeat.core.aggregation import`
- `src/aeat/application/aggregation/_foreign_assets.py` — same
- `src/aeat/application/aggregation/_retenciones.py` — same
- `src/aeat/application/aggregation/_service.py` — same
- `src/aeat/application/review/_operator.py` — `from ..aggregation._source_kinds import` → `from aeat.core.aggregation import`

## Files touched

- `src/aeat/application/aggregation/_counterpart.py`
- `src/aeat/application/aggregation/_foreign_assets.py`
- `src/aeat/application/aggregation/_retenciones.py`
- `src/aeat/application/aggregation/_service.py`
- `src/aeat/application/review/_operator.py`
- `src/aeat/application/aggregation/_source_kinds.py` (deleted)

## Verification

No shim re-export left. No remaining import of `_source_kinds` confirmed by grep and S327 inventory test.
