---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-06'
modified: '2026-05-06'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
  - '[[2026-05-06-calculation-truth-registry-invoice-row-bindings-exec]]'
---



# `calculation-truth-registry` `invoice row indexes`

Aligned invoice repeated-row binding outputs with the filing draft row-index
contract.

- Modified: `src/aeat/domain/calculations/registry/_bindings.py`
- Modified: `src/aeat/domain/calculations/registry/test_invoice_bindings.py`
- Modified: `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Description

`resolve_invoice_binding_row_values` now emits one-based row indexes. This
matches `FilingBindingValue.row_index` and the fixed-width export renderer,
which already treats repeated binding rows as positive row numbers.

## Tests

- `uv run pytest src/aeat/domain/calculations/registry/test_invoice_bindings.py -q`
- `uv run ty check src/aeat/domain/calculations/registry/_bindings.py src/aeat/domain/calculations/registry/test_invoice_bindings.py`
- `uv run ruff check src/aeat/domain/calculations/registry/_bindings.py src/aeat/domain/calculations/registry/test_invoice_bindings.py`
- `git diff --check -- src/aeat/domain/calculations/registry/_bindings.py src/aeat/domain/calculations/registry/test_invoice_bindings.py`
