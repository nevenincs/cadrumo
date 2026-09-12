---
tags:
  - '#exec'
  - '#binding-schema'
date: '2026-09-12'
modified: '2026-09-12'
body_schema: 'body-v2'
body_hash: 'sha256:cfa68921eb10107142807b6dfee4ef3ad566cd37db1581c1d882b3cd4cec8d25'
step_id: 'S30'
related:
  - "[[2026-09-11-binding-schema-plan]]"
---
# Author the edition-level binding_source_refs and formula_source_refs manifest defaults for every edition the signal reports as family_default_undeclared (58 binding editions, 54 formula editions), lifting the ref every member states to the manifest and dropping the restated member refs, driving family_default_undeclared to 0

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/*/revisions/*/revision.toml`
- `src/cadrumo/_data/registry/aeat/modelos/*/revisions/*/bindings/*.toml`
- `src/cadrumo/_data/registry/aeat/modelos/*/revisions/*/formulas/*.toml`
- `dev/registry/rename_formula_binding_identifiers.py`

## Changes

- `A` `dev/registry/lift_family_source_defaults.py`
- `A` `dev/registry/tests/test_lift_family_source_defaults.py`
- `M` `justfile`
- `M` `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2023/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2023/formulas/0001-formulas.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2023/bindings/0001-bindings.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2023/bindings/0002-domestic-base.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2023/bindings/0003-rate-box-layer.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2023/bindings/0004-recargo-rate-box-layer.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2023/bindings/0005-volumen-operaciones.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2023/bindings/0006-aic-rate-box-layer.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2023/bindings/0007-domestic-reverse-charge.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2023/bindings/0008-aic-rate-blind-base.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2023/bindings/0009-m303-regimen-simplificado-annual-summary.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2023/bindings/0010-page-07-prorratas.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2023/bindings/0011-page-05-regimen-simplificado.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2023/bindings/0012-page-01-declared.toml`
- `verify:` `just report-registry-edition-delta-status --lines --totals-only` -> `pass`
- `verify:` `uv run --no-sync pytest dev/registry/tests/test_lift_family_source_defaults.py` -> `pass`
- `verify:` `uv run --no-sync ruff check dev/registry/lift_family_source_defaults.py dev/registry/tests/test_lift_family_source_defaults.py` -> `pass`
- `verify:` `uv run --no-sync ty check dev/registry/lift_family_source_defaults.py dev/registry/tests/test_lift_family_source_defaults.py` -> `pass`

## Notes

The step's 112 candidate editions were reduced to 4 by a concurrent writer before this pass applied; this pass wrote 390/2023 only. 180/2023-y-siguientes remains unlifted because its revision.toml is dirty under another writer's predecessor migration, and 576/2007 is a different condition (edition_default_underivable) for which no disposition key exists in the schema or the screen. The signal now reports family_default_undeclared=2.

The disposition key the prior pass found missing now exists. `ModeloRevision` carries a
MANIFEST_ONLY `source_default_dispositions: Mapping[str, SourceDefaultDisposition]`
(FROZEN_MAPPING), keyed on the families that carry an edition source default -
`casillas`, `bindings`, `formulas` - with the value model in the new public module
`src/cadrumo/domain/calculations/registry/source_default_dispositions.py`
(`kind: Literal["underivable"]`, non-empty `reason`). A model validator refuses a key
naming no source-default family and refuses a disposition for a family whose default the
same edition declares. The allowed-key set is read from `FAMILY_SOURCE_DEFAULT_FIELDS`
plus the casilla family at call time, because `reference_sections` reaches the schema
through the reference checker and a module-level import would close that cycle.

Modelo 576 has no bindings and no formulas in edition 2007, and the screen's only
underivable finding there is the edition-level (casilla) one, detail `no leading
source_refs run is shared by two rows`. The authored disposition is therefore the
`casillas` key, not `bindings` or `formulas`: the edition authors a single
source-stating casilla row, so one statement can open no run a second shares. The key
path for the screen to read is
`revisions."2007".source_default_dispositions.casillas` in
`src/cadrumo/_data/registry/aeat/modelos/576/revisions/2007/revision.toml`, carrying
`kind` and `reason`.

- `M` `src/cadrumo/domain/calculations/registry/schema.py`
- `A` `src/cadrumo/domain/calculations/registry/source_default_dispositions.py`
- `M` `src/cadrumo/_data/registry/aeat/modelos/576/revisions/2007/revision.toml`
- `A` `dev/registry/tests/test_revision_source_default_dispositions.py`
- `M` `dev/registry/tests/test_revision_manifest_only_placement.py`
- `verify:` `uv run pytest dev/registry/tests/test_revision_source_default_dispositions.py -n 0` -> `3 passed` (exit 0)
- `verify:` `uv run pytest dev/registry/tests/test_revision_manifest_only_placement.py dev/registry/tests/test_revision_family_source_defaults.py -n 0` -> `31 passed, 1 failed` (exit 1; the failure is the pre-existing `cadrumo-authority-artifact-v3`/`v4` republication gap owned by a concurrent writer)
- `verify:` `uv run ruff check` + `uv run ruff format --check` on the five touched Python files -> `pass` (exit 0)
- `verify:` `uv run ty check` on the three changed source/test modules -> `All checks passed` (exit 0)
- `verify:` `uv run basedpyright` on the four touched Python files -> `0 errors, 0 warnings` (exit 0)
- `verify:` `load_modelo_directory` over modelo 576 -> edition 2007 resolves `{'casillas': ('underivable', ...)}`, 2008-y-siguientes empty (exit 0)

- `M` `src/cadrumo/_data/registry/aeat/modelos/036/revisions/2025-02-03-y-siguientes/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/115/revisions/2019-y-siguientes/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/128/revisions/2019-y-siguientes/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/369/revisions/esquema-exterior/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/369/revisions/esquema-importacion/revision.toml`
- `M` `src/cadrumo/_data/registry/aeat/modelos/369/revisions/esquema-union/revision.toml`
- `verify:` `load_modelo_directory` over modelos 036, 115, 128, 369 -> all load (exit 0)
- `note:` four reported editions deferred as dirty under another writer: 151/2015-2022, 151/2025-y-siguientes (bindings), 202/2019-2022, 202/2023-2024 (bindings)

- restated-bindings strip prepared: a dry-run-only tool that removes a successor edition's
  binding members restating the member the keyed merge would inherit, proven byte-identical
  against the loader's own keyed-merge function called with a locally built `bindings`
  family; the live proof through `load_modelo_directory` re-runs after the family is
  enrolled in the materialiser. Nothing under `src/cadrumo/_data` was written.
- `A` `dev/registry/strip_restated_bindings.py`
- `A` `dev/registry/tests/test_strip_restated_bindings.py`
- `M` `justfile`
- `verify:` `uv run --no-sync pytest dev/registry/tests/test_strip_restated_bindings.py` -> `6 passed` (exit 0)
- `verify:` `uv run --no-sync ruff check` + `ruff format` on both files -> `pass` (exit 0)
- `verify:` `uv run --no-sync ty check` on both files -> `All checks passed` (exit 0)
- `verify:` `uv run --no-sync python -m dev.registry.strip_restated_bindings --all --dry-run --report ...` -> removable=523, kept_differs=1701, restated_after_lifting=1265, restated_ignoring_refs=1911, refusals=45 (exit 0)
