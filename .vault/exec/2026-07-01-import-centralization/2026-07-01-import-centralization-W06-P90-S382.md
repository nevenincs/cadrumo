---
tags:
  - '#exec'
  - '#import-centralization'
date: '2026-07-03'
modified: '2026-07-17'
step_id: 'S382'
related:
  - "[[2026-07-01-import-centralization-plan]]"
---

# Run pytest --collect-only -q across src/aeat and confirm clean collection with no import errors

## Scope

- `src/aeat`

## Description

Ran the campaign-close collection gate to confirm the import-centralization rewrites left the whole tree importable.

- Ran `uv run --no-sync pytest --collect-only -q src/aeat` and captured the full output to disk.
- Confirmed `12211/14833 tests collected (2622 deselected)` with zero collection-error summary lines and no `ImportError` / `ModuleNotFoundError` collection failures.

## Outcome

Collection is clean across `src/aeat`: 12211 tests collected in 37.86s, zero import errors. The facade-routing and cycle-break rewrites of this campaign introduced no unresolvable import at collection time. The 2622 deselected entries are the normal marker-based deselection, not errors.

## Notes

None. The gate is a read-only verification; no code changed.
