---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'S2309'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
---

# `cli-workflow-redesign` `W84.P406.S2309`

Audited registry TOML source declarations and migrated the only bare `invoice` model binding set to a canonical source kind.

- Modified: `registry/aeat/modelos/349.toml`

## Description

The audit found bare `source = "invoice"` declarations only in Modelo 349. Those bindings now use `source = "ledger_transaction"` and the stale export-layout comment now names canonical ledger transaction source facts.

## Tests

Validated by focused registry tests and a source declaration scan:

- `uv run --no-sync pytest -q src/aeat/domain/calculations/registry/test_counterpart_bindings.py src/aeat/domain/calculations/registry/test_modelo_349_registry.py src/aeat/domain/calculations/registry/test_registry_schema.py src/aeat/domain/calculations/registry/test_public_api_boundaries.py`
- `rg -n 'source = "invoice"' src registry`
