---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S03'
related:
  - '[[2026-05-27-schema-hardening-m184-standardization-plan]]'
---



# `schema-hardening-m184-standardization` `P01.S03`

Verified the Modelo 184 directory-fragment layout against focused and broader
registry gates, including M184 detail-record row behavior.

- Modified: `.vault/plan/2026-05-27-schema-hardening-m184-standardization-plan.md`
- Created: `.vault/exec/2026-05-27-schema-hardening-m184-standardization/2026-05-27-schema-hardening-m184-standardization-P01-S03.md`

## Description

The focused verification confirmed committed Modelo 184 validation, snapshot
selection, legal/source grounding, February deadline windows, read-only live
cross references, construct linkage, and filing schedule behavior still work
from the directory layout. Loader directory-mode tests confirmed single-file
and fragment-directory equivalence, stale sibling detection, committed
inventory, and TOML reviewability limits.

The broader gate added committed registry loading, referential integrity, and
the M184 detail-record row builder, row-set assembly, and round-trip surfaces
that consume the row-producer bindings.

Reviewability baseline after the split:

- `184.toml` no longer exists.
- Modelo 184 now has 13 TOML fragments.
- Largest Modelo 184 fragment: 95 lines.
- Largest remaining root-level single-file modelo: `193.toml` at 472 lines.

## Tests

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_modelo_184_registry.py src/aeat/domain/calculations/registry/test_loader_directory_mode.py -q`
- Result: 32 passed.

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_modelo_184_registry.py src/aeat/domain/calculations/registry/test_loader_directory_mode.py src/aeat/domain/calculations/registry/test_committed_registry.py src/aeat/domain/calculations/registry/test_referential_integrity.py src/aeat/domain/calculations/registry/test_detail_record_row_builders.py src/aeat/domain/calculations/registry/test_detail_record_modelo_coverage.py src/aeat/application/calculations/test_row_set_assembly.py src/aeat/application/calculations/test_detail_record_round_trip.py -q`
- Result: 157 passed.
