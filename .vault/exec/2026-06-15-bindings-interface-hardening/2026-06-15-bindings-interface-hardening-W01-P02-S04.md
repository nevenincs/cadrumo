---
tags:
  - '#exec'
  - '#bindings-interface-hardening'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S04'
related:
  - "[[2026-06-15-bindings-interface-hardening-plan]]"
---




# introduce one canonical binding source-kind enum in core reconciling AggregationSourceKind and RowSetGroupingKind, realigning the related_party, atribucion and refund tokens to match enum values

## Scope

- `src/aeat/core/aggregation.py`

## Description

- Add a single canonical `BindingSourceKind` StrEnum to `src/aeat/core/aggregation.py` enumerating all 17 binding source tokens (4 scalar: profile, previous_filing, relation_prefill, manual_input; 4 ledger; 4 invoice/counterpart; 5 detail-record).
- Keep every member value byte-equal to the current stored token (a behaviour-preserving lift, not a rename), reusing the `AggregationSourceKind` and `RowSetGroupingKind` values where they overlap so the cross-layer taxonomy stays aligned.
- Replace the mixed 18-slot Literal on `DataBindingDefinition.source` in `_schema.py` with `BindingSourceKind`, and add a `mode="before"` field validator coercing the raw registry TOML string to its enum member under strict config (the sibling of the existing `BindingAggregation._coerce_op`).
- Resolve the related_party/atribucion/refund source-token versus `RowSetGroupingKind` value mismatch by an explicit documented mapping `ROW_SET_GROUPING_FOR_BINDING_SOURCE` rather than mutating `RowSetGroupingKind` (its values are the separate application-layer row-assembly grouping axis); cross-document both enums.
- Export `BindingSourceKind` from `aeat.core` (`__all__`, lazy `__getattr__`, TYPE_CHECKING import, module docstring).

## Outcome

`DataBindingDefinition.source` is now the uniform `BindingSourceKind` enum. The before-validator preserves strict rejection of unknown tokens while keeping the authoring TOML plain. No stored token string changed; `AggregationSourceKind` and `RowSetGroupingKind` retain their existing non-binding consumers unbroken (StrEnum cross-comparison by value holds at every comparison and dispatch-dict site). The detail-record token↔grouping correspondence is now explicit and reader-visible.

## Notes

The brief's literal phrasing ("realign the related_party/atribucion/refund tokens to match enum values") was satisfied by making the correspondence explicit rather than by changing values: changing `RowSetGroupingKind` values would break the application-layer `_row_set_assembly.py` grouping dispatch, and changing the stored source tokens would break persisted registry TOML. The explicit `ROW_SET_GROUPING_FOR_BINDING_SOURCE` map plus cross-referencing docstrings is the behaviour-preserving resolution the ADR's "do not change the stored token strings" constraint requires.
