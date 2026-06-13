---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-31'
modified: '2026-05-31'
step_id: 'S529'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# `codebase-solidification` `W07.P33.S529`

REGRESSION FIX: re-placed `CAST-RATIONALE-LEDGER-COUNTERPART-SOURCEKIND` marker inline at `src/aeat/domain/calculations/registry/_bindings.py` line 1660 (the `cast()` call site).

- Modified: `src/aeat/domain/calculations/registry/_bindings.py`

## Description

Root cause of drift: the W6 placement put the rationale marker in a three-line comment block (lines 1656-1658) above the `source_kind` field declaration (line 1659). The `cast(` call is inside the `Field(default=...)` argument on line 1660. The inventory test's upward scan from line 1660 halted at line 1659 (a code line, not a comment/blank), so it never reached the marker block at 1656-1658.

Fix: removed the preceding comment block and placed the rationale inline on the `cast(` line itself — the test's same-line check fires immediately.

The `test_cast_rationale_inventory.py::test_every_cast_has_rationale_marker` test now passes and acts as a grep-post-condition for future marker drift.

## Tests

`test_cast_rationale_inventory.py::test_every_cast_has_rationale_marker` — was FAILED before fix, now PASSED.

All 4 tests in the combined run passed cleanly.
