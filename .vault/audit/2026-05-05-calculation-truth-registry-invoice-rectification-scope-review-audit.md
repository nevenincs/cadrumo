---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
  - '[[2026-05-05-calculation-truth-registry-invoice-rectification-scope-exec]]'
---



# `calculation-truth-registry` Code Review

No blocking issues were found in the invoice rectification-scope hardening
slice.

The change is narrow and central: `_bindings.py` rejects
`rectified_base_delta_sum` unless the binding selector declares
`rectification_scope = only_rectifications`. That removes an observation-stream
dependent runtime condition from the calculation path.

The added test mutates the committed Modelo 130 registry object and verifies
`RegistryValidator` rejects the malformed invoice binding. A focused runtime
test still proves the valid rectification-delta path calculates correctly.

Verification recorded:

- `uv run pytest src/aeat/domain/calculations/registry/test_registry_schema.py::test_validator_rejects_invoice_rectification_delta_without_rectification_scope src/aeat/domain/calculations/registry/test_invoice_bindings.py::test_resolve_invoice_binding_values_computes_rectification_delta_sum -q`
- `uv run ty check src/aeat/domain/calculations/registry/_bindings.py src/aeat/domain/calculations/registry/test_registry_schema.py src/aeat/domain/calculations/registry/test_invoice_bindings.py`
- `uv run ruff check src/aeat/domain/calculations/registry/_bindings.py src/aeat/domain/calculations/registry/test_registry_schema.py src/aeat/domain/calculations/registry/test_invoice_bindings.py`
- `git diff --check -- src/aeat/domain/calculations/registry/_bindings.py src/aeat/domain/calculations/registry/test_registry_schema.py`
