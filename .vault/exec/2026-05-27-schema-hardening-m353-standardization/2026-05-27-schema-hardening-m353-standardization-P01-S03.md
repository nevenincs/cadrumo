---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S03'
related:
  - '[[2026-05-27-schema-hardening-m353-standardization-plan]]'
---



# `schema-hardening-m353-standardization` `P01.S03`

Verified the Modelo 353 directory-fragment layout against focused and broader
registry gates.

- Modified: `.vault/plan/2026-05-27-schema-hardening-m353-standardization-plan.md`
- Created: `.vault/exec/2026-05-27-schema-hardening-m353-standardization/2026-05-27-schema-hardening-m353-standardization-P01-S03.md`

## Description

The focused verification confirmed committed Modelo 353 validation, monthly
snapshot selection, filing deadlines, live cross-reference write forbiddance,
construct linkage, and IVA aggregation binding resolution still work from the
directory layout. Loader directory-mode tests confirmed single-file and
fragment-directory equivalence, stale sibling detection, committed inventory,
and TOML reviewability limits.

The broader registry gate added committed registry loading, referential
integrity, and IVA ledger aggregation binding coverage across the affected
surface.

Reviewability baseline after the split:

- `353.toml` no longer exists.
- Modelo 353 now has 14 TOML fragments.
- Largest Modelo 353 fragment: 104 lines.
- Largest remaining root-level single-file modelo: `184.toml` at 483 lines.

## Tests

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_modelo_353_registry.py src/aeat/domain/calculations/registry/test_loader_directory_mode.py -q`
- Result: 33 passed.

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_modelo_353_registry.py src/aeat/domain/calculations/registry/test_loader_directory_mode.py src/aeat/domain/calculations/registry/test_committed_registry.py src/aeat/domain/calculations/registry/test_referential_integrity.py src/aeat/domain/calculations/registry/test_ledger_iva_aggregation_binding.py -q`
- Result: 142 passed.
