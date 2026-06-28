---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
  - '[[2026-05-05-calculation-truth-registry-invoice-binding-validation-exec]]'
---



# `calculation-truth-registry` `invoice rectification scope`

Hardened invoice-source binding validation so `rectified_base_delta_sum`
bindings cannot rely on the caller's observation stream to contain only
rectifications. The selector itself must declare `only_rectifications`.

- Modified: `src/aeat/domain/calculations/registry/_bindings.py`
- Modified: `src/aeat/domain/calculations/registry/test_registry_schema.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Description

The invoice binding validator now treats rectification delta calculation as a
selector contract. A registry definition that declares the rectification delta
fact without an explicit rectification-only scope fails validation before
snapshot or calculation use.

The behavior test mutates the committed registry object and verifies the real
`RegistryValidator` failure path.

## Tests

- `uv run pytest src/aeat/domain/calculations/registry/test_registry_schema.py::test_validator_rejects_invoice_rectification_delta_without_rectification_scope src/aeat/domain/calculations/registry/test_invoice_bindings.py::test_resolve_invoice_binding_values_computes_rectification_delta_sum -q`
- `uv run ty check src/aeat/domain/calculations/registry/_bindings.py src/aeat/domain/calculations/registry/test_registry_schema.py src/aeat/domain/calculations/registry/test_invoice_bindings.py`
- `uv run ruff check src/aeat/domain/calculations/registry/_bindings.py src/aeat/domain/calculations/registry/test_registry_schema.py src/aeat/domain/calculations/registry/test_invoice_bindings.py`
- `git diff --check -- src/aeat/domain/calculations/registry/_bindings.py src/aeat/domain/calculations/registry/test_registry_schema.py`
