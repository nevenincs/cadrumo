---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-31'
modified: '2026-05-31'
step_id: 'S530'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# `codebase-solidification` `W07.P33.S530`

Real-behavior verification test file created at `src/aeat/test_w07_p33_cleanup.py` asserting S528 deletion and the W2 cast-rationale inventory contract.

- Created: `src/aeat/test_w07_p33_cleanup.py`

## Description

Three real-behavior tests — no mocks, no skips, no xfail:

- `test_aeat_core_time_module_deleted`: calls `importlib.import_module("aeat.core._time")` and asserts `ModuleNotFoundError`. Proves the deletion landed and no `.pyc` or namespace package survivor exists.
- `test_no_source_imports_aeat_core_time`: walks all production source files and asserts none reference `"aeat.core._time"`. Guards against future re-introduction.
- `test_every_production_cast_has_rationale_marker`: re-runs the W2 inventory contract (AST walk + upward scan) across all production modules. Fails fast if any `cast(` call lacks a `CAST-RATIONALE-*` marker.

## Tests

All 4 tests (`test_cast_rationale_inventory.py` × 1 + `test_w07_p33_cleanup.py` × 3) passed in a single `pytest -xvs` run. No mocks, no patches, no tautological assertions.
