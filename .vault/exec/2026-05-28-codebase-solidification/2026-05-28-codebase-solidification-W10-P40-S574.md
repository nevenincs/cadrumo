---
step_id: S574
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# codebase-solidification W10.P40.S574 — W10.P40 constants inventory test

## Outcome

Created `src/aeat/test_w10_p40_constants_inventory.py` with 4 AST-level
structural tests:

- `test_no_bare_varchar64_in_secure_objects`: asserts ≤1 bare `"VARCHAR(64)"`
  in `secure_objects.py` (only the constant definition allowed).
- `test_no_bare_libreoffice_engine_in_workbook_parity`: asserts ≤2 bare
  `"libreoffice-headless"` in `_workbook_parity.py` (Literal alias + constant def).
- `test_workbook_kind_is_strenum_with_all_members`: runtime check that
  `WorkbookKind` is a `StrEnum` subclass with all 6 canonical members enrolled.
- `test_workbook_kind_enum_members_in_ast`: AST check that all 6 member
  values appear as class-body assignments in source.

All 4 tests pass. Full suite count: 63 tests pass (including 18 workbook parity,
38 secure objects SQL, 3 single-surface invariant).

## Commit

`5cc2fffd6`
