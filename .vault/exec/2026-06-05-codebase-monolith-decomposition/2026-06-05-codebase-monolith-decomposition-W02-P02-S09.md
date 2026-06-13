---
tags: ['#exec', '#codebase-monolith-decomposition']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S09'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P02.S09 - residual ledger slice selection

Scope: `src/aeat/entrypoints/cli/_ledger.py`.

## Description

- Ran exact `rg` discovery for `inventory_app`, `inventory_movement_app`, `inventory_valuation_app`, `_inventory_`, and `Inventory`.
- Ran semantic `vaultspec-rag` code search for the inventory command group.
- Selected the inventory noun group as the next residual ledger extraction slice.

## Outcome

The selected slice covered:

```text
inventory_app
inventory_movement_app
inventory_valuation_app
_inventory_service
inventory_list
inventory_create
inventory_movement_add
inventory_valuation_preview
```

Exact discovery found dedicated real-behavior tests in `test_inventory_verbs.py`. Those tests import `inventory_app` from `_ledger.py`, so the extraction had to preserve the ledger top-level facade export.

RAG search succeeded through the running service and identified the same inventory command decorators and app registration area. The search result contained duplicate stale line anchors, so exact `rg` and direct file reads were used as the authoritative source for current line positions.

## Notes

No production files were changed in this selection step.
