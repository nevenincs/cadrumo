---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'S2305'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
---

# `cli-workflow-redesign` `W84.P405.S2305`

Implemented the primary W84 registry taxonomy enforcement slice. Companion execution records link the adjacent completed audit and verification steps.

- Modified: `src/aeat/domain/calculations/registry/_schema.py`
- Modified: `src/aeat/domain/calculations/registry/_validate.py`
- Modified: `src/aeat/domain/calculations/registry/_bindings.py`
- Modified: `src/aeat/domain/calculations/registry/__init__.py`
- Modified: `registry/aeat/modelos/349.toml`
- Modified: `src/aeat/domain/calculations/registry/test_modelo_349_registry.py`
- Modified: `src/aeat/domain/calculations/registry/test_registry_schema.py`
- Modified: `src/aeat/domain/calculations/registry/test_public_api_boundaries.py`
- Created: `src/aeat/domain/calculations/registry/test_counterpart_bindings.py`
- Removed: `src/aeat/domain/calculations/registry/test_invoice_bindings.py`

## Description

The registry schema now rejects bare `invoice` binding sources at model-load time with a typed validation message naming the four canonical source kinds: `ledger_transaction`, `purchase_invoice_evidence`, `payable_invoice`, and `collectible_invoice`. The registry validator keeps the same guard for mutated in-memory definitions.

The previous invoice-source binding helper surface was removed from the public registry API and replaced with counterpart aggregation helpers. Modelo 349 bindings were migrated from `source = "invoice"` to `source = "ledger_transaction"`, preserving the existing real aggregation behavior for summary and Tipo 2 row values while removing the deprecated source kind.

## Tests

Focused registry verification passed:

- `uv run --no-sync pytest -q src/aeat/domain/calculations/registry/test_counterpart_bindings.py src/aeat/domain/calculations/registry/test_modelo_349_registry.py src/aeat/domain/calculations/registry/test_registry_schema.py src/aeat/domain/calculations/registry/test_public_api_boundaries.py`

Additional checks:

- `uv run --no-sync pytest --collect-only -q src/aeat/application/aggregation`
- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md --json`
- Symbol scan found no remaining old invoice binding public API references.

`uv run --no-sync vaultspec-core vault check all` still reports pre-existing vault-wide structure, feature-index, and schema issues unrelated to this W84 slice.
