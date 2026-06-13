---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S25'
related:
  - '[[2026-05-20-calculation-source-connectivity-plan]]'
---

# `calculation-source-connectivity` `W02.P05.S25`

Adapted governed invoice catalogue observations into source-mesh resolution.

- Created: `src/aeat/application/invoices/_source_resolver.py`
- Created: `src/aeat/application/invoices/test_source_resolver.py`
- Modified: `src/aeat/application/invoices/__init__.py`
- Modified: `.vault/plan/2026-05-20-calculation-source-connectivity-plan.md`

## Description

Added `InvoiceCatalogueSourceResolver`, a repository-backed source resolver that owns `collectible_invoice` and `payable_invoice` source kinds. The resolver loads the encrypted invoice catalogue, filters invoices by bucket and filing period, converts supported intra-community issued/received invoices into registry `InvoiceObservation` records, resolves scalar invoice binding values, and emits source refs, linked transaction ids, and SHA-256 fingerprints for observed invoice facts.

This is the scalar first slice for `InvoiceCatalogue` enrollment. The source mesh contract still needs explicit row-value transport before row-producing Modelo 349 invoice bindings can be carried through calculation/export paths.

## Tests

Ran `uv run pytest src/aeat/application/invoices/test_source_resolver.py`: 1 passed.

Ran `uv run --no-sync ruff check src/aeat/application/invoices/_source_resolver.py src/aeat/application/invoices/test_source_resolver.py src/aeat/application/invoices/__init__.py`: all checks passed.
