---
step_id: S570
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W10.P40.S570 — WorkbookKind Literal to StrEnum

## Outcome

Promoted `WorkbookKind` from a `Literal[...]` type alias to a `StrEnum`
in `src/aeat/domain/calculations/registry/_workbook_parity.py`, following
the same pattern as `WorkbookScanStatus`.

Six members: `FORMULA_FORM`, `RECORD_DESIGN_LAYOUT`, `VALIDATION_HINTS`,
`STATIC_LAYOUT`, `UNSUPPORTED_BINARY_XLS`, `UNREADABLE`.

Migrated all comparison and assignment callsites:
- Line 122 (set-literal validator): bare strings replaced with enum members
- Lines 367, 374 (`_xls_short_circuit_report`): UNSUPPORTED_BINARY_XLS
- Line 734 (formula_form guard): FORMULA_FORM
- Lines 964, 965, 1016, 1018 (coverage counts): enum members
- `_classify_xlsx` returns: all four enum members
- `_evidence_for_workbook_kind` comparisons: all enum members
- Two `workbook_kind="unreadable"` sites: UNREADABLE

## Grep post-condition

- Before: 8+ bare WorkbookKind string comparison/assignment callsites
- After: 0 bare callsites (StrEnum member definitions only remain)

## Commit

`5cc2fffd6`
