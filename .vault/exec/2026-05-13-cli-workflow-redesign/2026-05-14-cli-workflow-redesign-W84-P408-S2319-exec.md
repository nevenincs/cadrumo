---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'S2319'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
---

# `cli-workflow-redesign` `W84.P408.S2319`

Added registry tests that lock bare `invoice` rejection and removed invoice compatibility API exposure.

- Modified: `src/aeat/domain/calculations/registry/test_registry_schema.py`
- Modified: `src/aeat/domain/calculations/registry/test_public_api_boundaries.py`
- Created: `src/aeat/domain/calculations/registry/test_counterpart_bindings.py`
- Removed: `src/aeat/domain/calculations/registry/test_invoice_bindings.py`

## Description

Tests now cover schema-load rejection, registry validator rejection, absence of old invoice public API names, and counterpart source-kind filtering across canonical source kinds.

## Tests

Focused registry verification passed:

- `uv run --no-sync pytest -q src/aeat/domain/calculations/registry/test_counterpart_bindings.py src/aeat/domain/calculations/registry/test_modelo_349_registry.py src/aeat/domain/calculations/registry/test_registry_schema.py src/aeat/domain/calculations/registry/test_public_api_boundaries.py`
