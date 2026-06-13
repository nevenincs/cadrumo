---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
  - '[[2026-05-05-calculation-truth-registry-invoice-source-bindings-exec]]'
---



# `calculation-truth-registry` `invoice binding validation`

Added fail-fast registry validation for invoice-source binding definitions so
malformed selectors and invalid fact or aggregation pairs are rejected before
snapshot construction or calculation runtime use.

- Modified: `src/aeat/domain/calculations/registry/_bindings.py`
- Modified: `src/aeat/domain/calculations/registry/_validate.py`
- Modified: `src/aeat/domain/calculations/registry/__init__.py`
- Modified: `src/aeat/domain/calculations/registry/test_registry_schema.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Description

`validate_invoice_binding_definition` centralizes invoice binding selector and
aggregation checks in the binding backend. `RegistryValidator` now calls it for
every registry binding whose source is `invoice`, which moves unsupported
invoice facts and aggregation mismatches out of late runtime failure paths.

The added tests mutate the committed Modelo 130 registry object and validate
the real registry validator response. They do not create a replacement modelo
schema inside the test suite.

## Tests

- `uv run pytest src/aeat/domain/calculations/registry/test_registry_schema.py src/aeat/domain/calculations/registry/test_invoice_bindings.py -q`
- `uv run ty check src/aeat/domain/calculations/registry/_bindings.py src/aeat/domain/calculations/registry/_validate.py src/aeat/domain/calculations/registry/__init__.py src/aeat/domain/calculations/registry/test_registry_schema.py src/aeat/domain/calculations/registry/test_invoice_bindings.py`
- `uv run ruff check src/aeat/domain/calculations/registry/_bindings.py src/aeat/domain/calculations/registry/_validate.py src/aeat/domain/calculations/registry/__init__.py src/aeat/domain/calculations/registry/test_registry_schema.py src/aeat/domain/calculations/registry/test_invoice_bindings.py`
- `git diff --check -- src/aeat/domain/calculations/registry/_bindings.py src/aeat/domain/calculations/registry/_validate.py src/aeat/domain/calculations/registry/__init__.py src/aeat/domain/calculations/registry/test_registry_schema.py`
