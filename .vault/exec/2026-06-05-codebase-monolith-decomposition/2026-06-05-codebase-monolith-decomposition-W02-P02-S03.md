---
tags: ['#exec', '#codebase-monolith-decomposition']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S03'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P02.S03 - ledger slice selection

Scope: `src/aeat/entrypoints/cli/_ledger.py`.

## Description

- Ran exact `rg` discovery for `payable_invoice`, `collectible_invoice`, `business_invoice`, `work_unit_id`, and `calculation_revision_id` across the ledger CLI and CLI tests.
- Ran semantic discovery with `vaultspec-rag` for payable and collectible invoice command registrar flow.
- Selected the payable and collectible business invoice command groups as the next coherent extraction slice.

## Outcome

The selected slice covered:

```text
_business_invoice_payload
_business_invoice_text_lines
_payable_invoice_service
_collectible_invoice_service
payable_invoice_app
collectible_invoice_app
payable_invoice_add/view/list/update/remove
collectible_invoice_add/view/list/update/remove
```

Exact discovery found the dedicated real-behavior CLI tests in `test_business_invoice_verbs.py`. The tests import `payable_invoice_app` and `collectible_invoice_app` from `_ledger.py`, so the extraction needed to preserve those top-level exports.

RAG search against `_ledger.py` confirmed the same decorated command bodies as the semantic slice. A first RAG attempt timed out at the default 10 second budget; the retried query succeeded with `--timeout 45`.

## Notes

No file edits were made in this selection step.
