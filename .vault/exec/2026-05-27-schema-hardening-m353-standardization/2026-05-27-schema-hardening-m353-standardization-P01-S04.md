---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S04'
related:
  - '[[2026-05-27-schema-hardening-m353-standardization-plan]]'
---



# `schema-hardening-m353-standardization` `P01.S04`

Recorded the M353 review outcome, final standardization baseline, and next
single-file normalization edge.

- Modified: `.vault/plan/2026-05-27-schema-hardening-m353-standardization-plan.md`
- Created: `.vault/audit/2026-05-27-schema-hardening-m353-standardization-review.md`
- Created: `.vault/exec/2026-05-27-schema-hardening-m353-standardization/2026-05-27-schema-hardening-m353-standardization-P01-S04.md`
- Created: `.vault/exec/2026-05-27-schema-hardening-m353-standardization/2026-05-27-schema-hardening-m353-standardization-P01-summary.md`

## Description

The final review found no M353 split defects. M353 now uses the same generic
manifest plus revision-fragment layout as the prior standardized modelos, with
no stale `353.toml` sibling and no per-modelo loader/schema code.

Final M353 baseline:

- `353.toml` does not exist.
- One fragment-directory revision exists: `2008-y-siguientes`.
- Modelo 353 has 14 TOML fragments.
- Largest Modelo 353 fragment: 104 lines.
- Largest remaining root-level single-file modelo: `184.toml` at 483 lines.

## Tests

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_modelo_353_registry.py src/aeat/domain/calculations/registry/test_loader_directory_mode.py -q`
- Result: 33 passed.

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_modelo_353_registry.py src/aeat/domain/calculations/registry/test_loader_directory_mode.py src/aeat/domain/calculations/registry/test_committed_registry.py src/aeat/domain/calculations/registry/test_referential_integrity.py src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py -q`
- Result: 142 passed.

- Rerun after reviewer caveat: same scoped broad gate, 142 passed.

- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-27-schema-hardening-m353-standardization-plan.md`
- Result: passed.
