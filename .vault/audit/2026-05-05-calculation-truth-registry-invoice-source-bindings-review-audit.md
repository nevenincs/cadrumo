---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
  - '[[2026-05-05-calculation-truth-registry-invoice-source-bindings-exec]]'
---



# `calculation-truth-registry` Code Review

No blocking issues were found in the invoice-source binding backend slice.

The resolver is centralized in `_bindings.py` and accepts only typed
`InvoiceObservation` inputs plus selectors declared by registry
`DataBindingDefinition` rows. It returns Decimal aggregates keyed by binding id
and ignores non-invoice bindings. The tests exercise validation, selector
filtering, aggregation behavior, rectification deltas, unsupported facts, and
operation mismatch failures.

The implementation does not encode target casillas, rates, legal treatment, or
modelo-specific formulas in code.

Verification recorded:

- `uv run pytest src/aeat/domain/calculations/registry/test_invoice_bindings.py -q`
- `uv run ty check src/aeat/domain/calculations/registry/_bindings.py src/aeat/domain/calculations/registry/test_invoice_bindings.py`
- `uv run ruff check src/aeat/domain/calculations/registry/_bindings.py src/aeat/domain/calculations/registry/test_invoice_bindings.py`
