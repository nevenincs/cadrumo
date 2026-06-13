---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-31'
modified: '2026-05-31'
step_id: S496
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# codebase-solidification W06.P30.S496

Regression fix: add `CAST-RATIONALE-LEDGER-COUNTERPART-SOURCEKIND` inline marker on the `cast()` call at `src/aeat/domain/calculations/registry/_bindings.py` (line introduced in W05.P25.S459 without the required marker).

- Modified: `src/aeat/domain/calculations/registry/_bindings.py`

## Description

The cast `cast(CounterpartSourceKind, AggregationSourceKind.LEDGER_TRANSACTION)` in the `CounterpartLedgerBinding.source_kind` field default was introduced in S459 without a `CAST-RATIONALE-*` marker, silently regressing the cast-rationale-inventory test discipline. The marker is placed inline on the cast line to satisfy the AST walker used by `test_cast_rationale_inventory.py`, which walks upward through only comment/blank lines — placing it on a preceding line separated by a code line (`Field(`) would not be found.

The marker text: `# CAST-RATIONALE-LEDGER-COUNTERPART-SOURCEKIND: bridging AggregationSourceKind StrEnum value to CounterpartSourceKind Literal alias; the runtime value is identical but the type system cannot infer the Literal subset.`

## Tests

`test_every_cast_has_rationale_marker` in `src/aeat/test_cast_rationale_inventory.py` passes after the inline marker is placed. Confirmed via `pytest src/aeat/test_cast_rationale_inventory.py` — 1 passed.
