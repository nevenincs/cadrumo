---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S03'
related:
  - '[[2026-05-27-schema-hardening-m115-standardization-plan]]'
---

# `schema-hardening-m115-standardization` `P01.S03`

Verified M115 directory loading, registry integrity, export behavior, and
file-size reduction after the split.

- Verified: `src/aeat/_data/registry/aeat/modelos/115`
- Verified: `src/aeat/domain/calculations/registry/test_modelo_115_registry.py`
- Verified: `src/aeat/domain/calculations/registry/test_committed_registry.py`
- Verified: `src/aeat/application/filing/test_export.py`

## Description

M115 now loads through the generic directory-mode loader with one
fragment-directory revision. The split reduced the M115 review surface from a
989-line single file to 14 TOML fragments, with the largest fragment at 525
lines.

Current registry file-size baseline:

- `115.toml` exists: false.
- M115 fragment count: 14.
- Largest M115 fragment: 525 lines.
- Largest remaining single-file modelo: M720 at 950 lines.

Remaining single-file modelos by line count:

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

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_modelo_115_registry.py src/aeat/domain/calculations/registry/test_modelo_115_round_trip.py src/aeat/domain/calculations/registry/test_loader_directory_mode.py src/aeat/domain/calculations/registry/test_committed_registry.py src/aeat/domain/calculations/registry/test_referential_integrity.py src/aeat/application/filing/test_filing.py::test_build_draft_uses_registry_snapshot_for_modelo_115 src/aeat/application/filing/test_filing.py::test_approve_modelo_115_draft_uses_registry_schema_fingerprint src/aeat/application/filing/test_export.py::test_export_writes_modelo_115_registry_layout src/aeat/application/filing/test_export.py::test_verify_matches_exported_modelo_115_layout src/aeat/application/verification/test_verify.py::test_verify_declaracion_uses_modelo_115_registry_snapshot -q`
- `120 passed in 121.12s`
