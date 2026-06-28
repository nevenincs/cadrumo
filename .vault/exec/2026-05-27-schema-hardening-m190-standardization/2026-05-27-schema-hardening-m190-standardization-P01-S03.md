---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S03'
related:
  - '[[2026-05-27-schema-hardening-m190-standardization-plan]]'
---

# `schema-hardening-m190-standardization` `P01.S03`

Verified M190 directory loading, registry integrity, relation resolution, and
file-size reduction after the split.

- Verified: `src/aeat/_data/registry/aeat/modelos/190`
- Verified: `src/aeat/domain/calculations/registry/test_modelo_190_registry.py`
- Verified: `src/aeat/domain/calculations/registry/test_committed_registry.py`
- Verified: `src/aeat/domain/calculations/registry/test_referential_integrity.py`

## Description

M190 now loads through the generic directory-mode loader with one
fragment-directory revision. The split reduced the M190 review surface from a
1,023-line single file to 15 TOML fragments, with the largest fragment at 285
lines.

Current registry file-size baseline:

- `190.toml` exists: false.
- M190 fragment count: 15.
- Largest M190 fragment: 285 lines.
- Largest TOML file currently observed in the registry: 1,618 lines.
- Largest remaining single-file modelo: M115 at 989 lines.

Remaining single-file modelos by line count:

- M115: 989
- M720: 950
- M390: 808
- M322: 573
- M353: 569
- M184: 483
- M193: 472
- M309: 363
- M347: 356
- M360: 324
- M036: 283
- M840: 210
- M308: 194

## Tests

Validation completed:

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_modelo_190_registry.py src/aeat/domain/calculations/registry/test_modelo_190_193_round_trip.py src/aeat/domain/calculations/registry/test_loader_directory_mode.py src/aeat/domain/calculations/registry/test_committed_registry.py src/aeat/domain/calculations/registry/test_referential_integrity.py src/aeat/domain/calculations/registry/test_modelo_chain_resolution.py src/aeat/domain/calculations/registry/test_detail_record_modelo_coverage.py src/aeat/domain/calculations/registry/test_cross_dependency_calculations.py::test_modelo_190_calculation_resolves_modelo_111_quarterly_filings -q`
- `134 passed in 119.36s`
