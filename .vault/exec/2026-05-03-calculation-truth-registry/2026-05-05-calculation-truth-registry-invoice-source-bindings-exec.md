---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
---



# `calculation-truth-registry` `invoice source bindings`

Added the shared invoice-source binding resolver used by IVA-oriented modelos
to aggregate factual invoice-ledger observations without moving casilla or legal
authority out of the registry definitions.

- Modified: `src/aeat/domain/calculations/registry/_bindings.py`
- Added: `src/aeat/domain/calculations/registry/test_invoice_bindings.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Description

`InvoiceObservation` is the normalized factual input shape for invoice-ledger
rows consumed by registry bindings. The resolver supports selector-driven
intra-community claves, rectification scope, optional VAT regime filtering,
base-amount aggregation, rectification deltas, and distinct operator counts.

The backend is modelo-agnostic. It resolves only binding facts declared by the
active registry revision and does not define target casillas, rates, legal
treatment, or filing formulas in code.

## Tests

- `uv run pytest src/aeat/domain/calculations/registry/test_invoice_bindings.py -q`
- `uv run ty check src/aeat/domain/calculations/registry/_bindings.py src/aeat/domain/calculations/registry/test_invoice_bindings.py`
- `uv run ruff check src/aeat/domain/calculations/registry/_bindings.py src/aeat/domain/calculations/registry/test_invoice_bindings.py`
