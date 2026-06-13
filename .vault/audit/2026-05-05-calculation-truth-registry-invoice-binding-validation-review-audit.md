---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
  - '[[2026-05-05-calculation-truth-registry-invoice-binding-validation-exec]]'
---



# `calculation-truth-registry` Code Review

No blocking issues were found in the invoice binding validation slice.

The registry validator now rejects malformed invoice selectors and invalid
invoice fact or aggregation combinations before a registry snapshot can be
treated as usable. The validation is implemented once in `_bindings.py` and
reused by requirement discovery and runtime resolution, so the public behavior
is consistent across introspection, validation, and calculation.

The tests exercise real `RegistryValidator` behavior by mutating the committed
Modelo 130 registry object. They verify failure on an invoice binding with no
typed `fact` selector and on an `operator_count` binding that uses the wrong
aggregation operation.

Verification recorded:

- `uv run pytest src/aeat/domain/calculations/registry/test_registry_schema.py src/aeat/domain/calculations/registry/test_invoice_bindings.py -q`
- `uv run ty check src/aeat/domain/calculations/registry/_bindings.py src/aeat/domain/calculations/registry/_validate.py src/aeat/domain/calculations/registry/__init__.py src/aeat/domain/calculations/registry/test_registry_schema.py src/aeat/domain/calculations/registry/test_invoice_bindings.py`
- `uv run ruff check src/aeat/domain/calculations/registry/_bindings.py src/aeat/domain/calculations/registry/_validate.py src/aeat/domain/calculations/registry/__init__.py src/aeat/domain/calculations/registry/test_registry_schema.py src/aeat/domain/calculations/registry/test_invoice_bindings.py`
- `git diff --check -- src/aeat/domain/calculations/registry/_bindings.py src/aeat/domain/calculations/registry/_validate.py src/aeat/domain/calculations/registry/__init__.py src/aeat/domain/calculations/registry/test_registry_schema.py`
