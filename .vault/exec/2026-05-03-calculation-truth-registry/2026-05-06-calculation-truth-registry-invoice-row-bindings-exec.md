---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-06'
modified: '2026-05-06'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
---



# `calculation-truth-registry` `factual invoice row bindings`

Added deterministic repeated-row invoice binding support for registry-backed
factual inputs. This is data plumbing only: legal treatment, casilla targets,
and formulas remain owned by modelo TOML definitions.

- Modified: `src/aeat/domain/calculations/registry/_bindings.py`
- Modified: `src/aeat/domain/calculations/registry/__init__.py`
- Modified: `src/aeat/domain/calculations/registry/test_invoice_bindings.py`
- Modified: `src/aeat/domain/calculations/registry/test_registry_schema.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Description

`resolve_invoice_binding_row_values` resolves invoice-source bindings whose
selector declares `fact = row_field` and whose aggregation declares `op = rows`.
Rows are grouped deterministically by `operator_clave` or
`operator_clave_period`, then exposed as `(binding_id, row_index)` values for
export or registry consumers that need repeated factual records.

Registry validation now rejects period-grouped invoice rows unless the selector
is scoped to rectification observations, because that grouping requires
rectified-year and rectified-period metadata.

## Tests

- `uv run pytest src/aeat/domain/calculations/registry/test_invoice_bindings.py src/aeat/domain/calculations/registry/test_registry_schema.py -q`
- `uv run ty check src/aeat/domain/calculations/registry/_bindings.py src/aeat/domain/calculations/registry/__init__.py src/aeat/domain/calculations/registry/test_invoice_bindings.py src/aeat/domain/calculations/registry/test_registry_schema.py`
- `uv run ruff check src/aeat/domain/calculations/registry/_bindings.py src/aeat/domain/calculations/registry/__init__.py src/aeat/domain/calculations/registry/test_invoice_bindings.py src/aeat/domain/calculations/registry/test_registry_schema.py`
- `git diff --check -- src/aeat/domain/calculations/registry/_bindings.py src/aeat/domain/calculations/registry/__init__.py src/aeat/domain/calculations/registry/test_invoice_bindings.py src/aeat/domain/calculations/registry/test_registry_schema.py`
