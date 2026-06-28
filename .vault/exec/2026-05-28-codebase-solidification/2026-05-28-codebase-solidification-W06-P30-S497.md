---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-31'
modified: '2026-05-31'
step_id: S497
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W06.P30.S497

Verify the cast-rationale-inventory test correctly catches the `_bindings.py` cast site.

- Modified: `src/aeat/domain/calculations/registry/_bindings.py` (via S496)

## Description

The inventory test `test_cast_rationale_inventory.py` uses an AST walker (`_cast_call_linenos`) that yields the line number of each `cast()` call node and then calls `_has_rationale_above` to scan the line itself plus immediately preceding comment/blank lines. The test correctly fired against the unmarked `_bindings.py:1652` site before S496 landed. After S496 placed the marker inline on the same line as the `cast(` call, the `if _RATIONALE_MARKER in line` guard on the cast line resolved it immediately.

Investigation outcome: no scope gap. The test walker uses `ast.walk(tree)` which traverses all nested `ast.Call` nodes, including those inside `Field(default=...)` keyword argument expressions. The sole issue was the marker comment being separated from the cast line by an intervening code line (`source_kind: CounterpartSourceKind = Field(`), which the upward-scan loop correctly treats as a stop condition.

## Tests

36 tests passed across `test_cast_rationale_inventory.py`, `test_family_parse_date.py`, and `test_counterpart_bindings.py`.
