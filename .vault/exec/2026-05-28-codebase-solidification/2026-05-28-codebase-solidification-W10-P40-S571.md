---
step_id: S571
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W10.P40.S571 — _ENGINE_LIBREOFFICE constant

## Outcome

Added `_ENGINE_LIBREOFFICE: WorkbookRunnerEngine = "libreoffice-headless"`
as a module-level constant in `_workbook_parity.py` (placed after the
`WorkbookRunnerEngine` Literal alias that defines the type).

Migrated 3 `engine="libreoffice-headless"` callsites to `engine=_ENGINE_LIBREOFFICE`:
- Line 477: `detect_workbook_runner` (settings-configured branch)
- Line 486: `detect_workbook_runner` (shutil.which branch)
- Line 844: `_resolve_libreoffice_for_run`

The `WorkbookRunnerEngine = Literal["libreoffice-headless", "excel-com"]`
type alias and the constant assignment are the only two remaining occurrences
of the bare string.

## Grep post-condition

- Before: 3 bare `"libreoffice-headless"` callsites in `_workbook_parity.py`
- After: 0 callsites (2 definitional occurrences remain: Literal type alias + constant def)

## Commit

`5cc2fffd6`
