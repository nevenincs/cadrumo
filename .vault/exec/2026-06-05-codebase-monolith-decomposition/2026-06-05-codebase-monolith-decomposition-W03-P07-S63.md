---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S63'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W03.P07.S63 Registry Binding Decomposition

Scope: `src/aeat/domain/calculations/registry/_bindings.py`, `src/aeat/domain/calculations/registry/*.py`.

## Description

- Split invoice-shaped binding behavior into `_invoice_bindings.py`.
- Split ledger aggregation binding behavior into `_ledger_bindings.py`.
- Split counterpart binding behavior into `_counterpart_bindings.py`.
- Split detail-record row binding behavior into `_detail_record_bindings.py`.
- Added `_binding_selector_utils.py` so split binding families share selector normalization.
- Preserved `_bindings.py` as the compatibility facade and selector-shape dispatcher.
- Preserved registry facade re-exports for public consumers.

## Outcome

`_bindings.py` reduced from roughly 2715 lines to 521 lines. All new binding-family modules remain below the 1250-line objective.

## Notes

The worktree already contained `_withholding_bindings.py`; this step preserved and used that existing extraction rather than replacing it.
