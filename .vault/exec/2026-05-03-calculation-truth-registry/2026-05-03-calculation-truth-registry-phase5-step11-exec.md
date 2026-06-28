---
tags:
  - '#exec'
  - '#calculation-truth-registry'
date: '2026-05-03'
modified: '2026-05-03'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-pending-adr]]'
---

# Phase 5 Step 11 Execution

Deleted application-local static filing schemas:

- Removed `src/aeat/application/filing/_testing_static_schema.py`.
- Removed `MODELO_130_SCHEMA`, `MODELO_303_SCHEMA`, `MODELO_390_SCHEMA`,
  `StaticCasillaCollection`, `StaticCasillaSchema`,
  `StaticCasillaSchemaProvider`, and `default_schema_provider` from
  `aeat.application.filing.testing`.
- Updated filing tests so registry-boundary paths no longer depend on
  model-specific synthetic schemas or formula definitions.
- Added non-model-specific in-test schema records for generic validator
  semantics: schema-version mismatch, required missing, range violation,
  and formula divergence.
- Strengthened deletion gates to prove the static schema module is physically
  absent, not importable, and not exported from the public testing helper
  surface.

Rationale:

- Test helpers may construct draft records for read-only reconciliation tests,
  but they must not carry model-specific filing schemas or formula truth.
- Generic validator behavior remains covered without reintroducing
  Modelo 130/303/390 synthetic authority.

Verification:

- `uv run --no-sync ruff check src\aeat\application\filing tests\import_contract\test_registry_deletion_gates.py`
- `uv run --no-sync ty check src\aeat\application\filing tests\import_contract\test_registry_deletion_gates.py`
- `uv run --no-sync pytest tests\import_contract\test_registry_deletion_gates.py src\aeat\application\filing`

Result: ruff passed, ty passed, and the focused pytest slice passed with
202 passed and 4 skipped.

Residual risk:

- Production schema/provider behavior remains intentionally fail-closed until
  validated registry snapshots are introduced.
