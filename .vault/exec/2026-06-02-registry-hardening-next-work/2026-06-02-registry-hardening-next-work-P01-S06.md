---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'P01.S06'
related:
  - '[[2026-06-02-registry-hardening-next-work-plan]]'
  - '[[2026-06-02-registry-hardening-fragment-headroom-audit]]'
---

# P01.S06 Execution Record

## Step

`P01.S06`: Split M100 2020 completeness manifest into fragments;
`src/aeat/_data/registry/aeat/modelos/100/revisions/2020`.

## Result

Completed. The former monolithic file was removed:

- `src/aeat/_data/registry/aeat/modelos/100/revisions/2020/completeness-manifest.toml`

It was replaced by the generic completeness fragment layout:

- `src/aeat/_data/registry/aeat/modelos/100/revisions/2020/completeness/0001-manifest.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2020/completeness/0002-casillas.part-001.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2020/completeness/0003-casillas.part-002.toml`
- `src/aeat/_data/registry/aeat/modelos/100/revisions/2020/completeness/0004-casillas.part-003.toml`

The generated fragments reconstruct the original file text exactly when read in
sorted loader order.

## Fragment Sizes

| Lines | Path |
| ---: | --- |
| 54 | `src/aeat/_data/registry/aeat/modelos/100/revisions/2020/completeness/0001-manifest.toml` |
| 600 | `src/aeat/_data/registry/aeat/modelos/100/revisions/2020/completeness/0002-casillas.part-001.toml` |
| 600 | `src/aeat/_data/registry/aeat/modelos/100/revisions/2020/completeness/0003-casillas.part-002.toml` |
| 134 | `src/aeat/_data/registry/aeat/modelos/100/revisions/2020/completeness/0004-casillas.part-003.toml` |

## Verification

- Fragment reconstruction check:
  - Result: `fragment reconstruction matches original`.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py::test_directory_mode_merges_completeness_manifest_casilla_fragments -q`
  - Result: 1 passed in 0.25s.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py::test_committed_registry_toml_files_stay_reviewable src/aeat/domain/calculations/registry/test_registry_reviewability.py::test_registry_toml_fragments_stay_reviewable -q`
  - Result: 2 passed in 5.30s.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py::test_committed_registry_tree_loads_directory_modelos -q`
  - Result: 1 passed in 27.04s.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py::test_committed_directory_source_inventory_lists_every_revision_fragment_toml -q`
  - Result: 1 passed in 20.98s.
- `uv run --no-sync python -c "from aeat.domain.calculations.registry import load_modelo_directory; from aeat.core.resources import bundled_path; m=load_modelo_directory(bundled_path('registry','aeat','modelos','100')); r=m.revisions['2020']; print(m.id, r.id, len(r.completeness_manifest.casillas))"`
  - Result: `100 2020 445`.
