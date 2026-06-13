---
step_id: S58
date: 2026-05-31
modified: '2026-05-31'
tags:
  - "#exec"
  - "#core-authority"
related:
  - "[[2026-05-31-core-authority-plan]]"
  - "[[2026-05-31-core-authority-adr]]"
---

# core-authority W06.P17.S58

## Summary

Exposed `AggregationSourceKind` via `core/__init__.py` using a module-level `__getattr__` lazy-import pattern. The symbol is now accessible as both `from aeat.core.aggregation import AggregationSourceKind` (existing canonical path) and `from aeat.core import AggregationSourceKind` (new shorter path), per PROMOTE-004 and Rule 1.

## Changes

`src/aeat/core/__init__.py`: Added `AggregationSourceKind` to `__all__` and implemented `__getattr__` lazy import to avoid the circular startup import chain (`core/__init__` → `aggregation` → `logging` → `dictConfig` → re-enters `core/__init__`).

The `__module__` attribute of `AggregationSourceKind` still reports `aeat.core.aggregation` (the definition site), satisfying the existing `test_aggregation_source_kind_canonical_module` enforcement test.

Existing callers (`from aeat.core.aggregation import AggregationSourceKind`) were not changed — the new path is additive.

## Test Results

11 existing core aggregation tests pass unchanged.

## Commit

`f970a83a1` — feat(core): W06.P17.S58 - expose AggregationSourceKind via core/__init__.py
