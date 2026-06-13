---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-06'
modified: '2026-05-06'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
  - '[[2026-05-06-calculation-truth-registry-invoice-row-bindings-exec]]'
---



# `calculation-truth-registry` Code Review

No blocking issues were found in the invoice row binding slice.

The implementation extends the existing centralized invoice binding backend
instead of adding a model-specific mapping. Repeated rows are resolved from
typed `InvoiceObservation` values and registry selectors only. The row resolver
does not know about modelo casillas, legal rates, tax treatment, or filing
formulas.

The main safety check is the period grouping guard: `operator_clave_period`
requires rectification-only scope before validation passes, avoiding a runtime
path where non-rectification observations could be accepted into a grouping
that needs rectified-period metadata.

Verification recorded:

- `uv run pytest src/aeat/domain/calculations/registry/test_invoice_bindings.py src/aeat/domain/calculations/registry/test_registry_schema.py -q`
- `uv run ty check src/aeat/domain/calculations/registry/_bindings.py src/aeat/domain/calculations/registry/__init__.py src/aeat/domain/calculations/registry/test_invoice_bindings.py src/aeat/domain/calculations/registry/test_registry_schema.py`
- `uv run ruff check src/aeat/domain/calculations/registry/_bindings.py src/aeat/domain/calculations/registry/__init__.py src/aeat/domain/calculations/registry/test_invoice_bindings.py src/aeat/domain/calculations/registry/test_registry_schema.py`
- `git diff --check -- src/aeat/domain/calculations/registry/_bindings.py src/aeat/domain/calculations/registry/__init__.py src/aeat/domain/calculations/registry/test_invoice_bindings.py src/aeat/domain/calculations/registry/test_registry_schema.py`
