---
step_id: S161
tags:
  - "#exec"
  - "#codebase-solidification"
date: 2026-05-28
modified: '2026-05-28'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
  - "[[2026-05-28-codebase-solidification-W01-P07-S160]]"
---

# codebase-solidification W01.P07.S161 — migrate bare-string input_kind comparisons to InputKind enum

## Outcome

Replaced all bare-string `input_kind == "..."` / `input_kind in (...)` / `input_kind != "..."` comparisons across 31 files with typed `InputKind.<MEMBER>` references. Deleted the obsolete `InputKind = Literal[...]` alias in `_modelo.py`. Upgraded `ModeloCasillaRow.input_kind` field type from `str` to `InputKind`.

## Files touched (production code)

- `src/aeat/application/filing/__init__.py` — 3 sites
- `src/aeat/application/modelo/_actions.py` — 8 sites
- `src/aeat/application/registry/__init__.py` — 2 sites + `InputKind` import alias
- `src/aeat/application/storage/calc_sheets/_engine.py` — 2 sites
- `src/aeat/application/storage/calc_sheets/_layout.py` — 2 sites
- `src/aeat/application/storage/calc_sheets/_parity_harness.py` — 3 sites
- `src/aeat/application/verification/_verify.py` — 2 sites
- `src/aeat/adapters/outbound/google/_calc_sheets_pull.py` — 2 sites
- `src/aeat/domain/calculations/registry/_bindings.py` — 1 site
- `src/aeat/domain/calculations/registry/_formula_runtime.py` — 5 sites
- `src/aeat/domain/calculations/registry/_queries.py` — 4 sites (incl. type annotation + DTO field)
- `src/aeat/domain/calculations/registry/_schema.py` — 4 sites (model_validator)
- `src/aeat/domain/calculations/registry/_validate_references.py` — 1 site
- `src/aeat/domain/calculations/registry/_validate_revision_rules.py` — 1 site
- `src/aeat/entrypoints/cli/_common.py` — 1 site (lazy local import)
- `src/aeat/entrypoints/cli/_modelo.py` — obsolete alias deleted, canonical import added

## Files touched (tests)

- `src/aeat/adapters/outbound/aeat/sede/test_declarations.py` — 2 sites
- `src/aeat/adapters/outbound/google/test_compute_from_pull.py` — 1 site
- `src/aeat/adapters/outbound/google/test_worksheet_export_pull_roundtrip.py` — 2 sites
- `src/aeat/application/modelo/test_file_flow.py` — 2 sites
- `src/aeat/application/modelo/test_verificado_completo_regression.py` — 1 site
- `src/aeat/domain/calculations/registry/test_census_modelo_registry_data.py` — 1 site
- `src/aeat/domain/calculations/registry/test_cross_dependency_contract.py` — 2 sites
- `src/aeat/domain/calculations/registry/test_modelo_100_registry.py` — 1 site
- `src/aeat/domain/calculations/registry/test_modelo_190_registry.py` — 1 site
- `src/aeat/domain/calculations/registry/test_modelo_200_temporal_coverage.py` — 2 sites
- `src/aeat/domain/calculations/registry/test_modelo_232_registry.py` — 1 site
- `src/aeat/domain/calculations/registry/test_modelo_347_registry.py` — 1 site
- `src/aeat/domain/calculations/registry/test_modelo_349_registry.py` — 1 site
- `src/aeat/domain/calculations/registry/test_modelo_720_registry.py` — 1 site
- `src/aeat/domain/calculations/registry/test_modelo_840_registry.py` — 1 site
- `src/aeat/domain/calculations/registry/test_queries.py` — 1 site

## Deferred / not migrated

- `src/aeat/application/filing/test_init.py` bare-string sides of cross-check assertions: intentional — they test the StrEnum == str contract, not production comparisons.
- `test_cross_dependency_contract.py::test_formula_relation_dependencies_are_attached_to_computed_casillas`: pre-existing registry-data failure (modelo 100 / renta-2024-pagos-fraccionados-ingresados); not introduced by this migration.

## Collision signal

One file (`_common.py`) had non-authored WIP at lines 85-90 (render_command_output refactor). My change was at line 320 — no conflict.

## Verification

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_schema.py src/aeat/domain/calculations/registry/test_queries.py src/aeat/domain/calculations/registry/test_modelo_349_registry.py src/aeat/domain/calculations/registry/test_modelo_200_temporal_coverage.py src/aeat/domain/calculations/registry/test_modelo_190_registry.py -q` → 99 passed
- Commit: `1aeb3aa41`
