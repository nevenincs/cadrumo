---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'P01.S08'
related:
  - '[[2026-06-02-registry-hardening-next-work-plan]]'
  - '[[2026-06-02-registry-hardening-m200-export-pressure-audit]]'
---

# P01.S08 Execution Record

## Step

`P01.S08`: Split the largest M200 export fragment if audit confirms safe
boundaries; `src/aeat/_data/registry/aeat/modelos/200`.

## Result

Completed. The former 1618-line fragment was removed:

- `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0028-modelo-200-page-019.part-002.toml`

It was replaced by two ordered record-field fragments:

- `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0028-modelo-200-page-019.part-002a.toml`
- `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0028-modelo-200-page-019.part-002b.toml`

The split follows the existing M200 page-019 fragment pattern. Both replacement
files repeat the export layout id and record id; `part-002a` carries the first
60 fields, and `part-002b` carries the remaining 57 fields.

## Fragment Sizes

| Lines | Fields | Path |
| ---: | ---: | --- |
| 834 | 60 | `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0028-modelo-200-page-019.part-002a.toml` |
| 790 | 57 | `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0028-modelo-200-page-019.part-002b.toml` |

The generated split was checked by reconstructing the original file text after
removing the repeated scaffold from `part-002b`.

## Corpus Pressure After Split

The largest committed TOML fragment is now:

- `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0065-modelo-200-page-043.toml`
  at 1612 lines.

The next pressure work therefore remains in M200 export after the already
tracked M303 audit step.

## Verification

- Split reconstruction check:
  - Result: `split reconstruction matches original`.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py::test_directory_mode_merges_export_record_field_fragments_by_record_id -q`
  - Result: 1 passed in 0.30s.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py::test_committed_registry_toml_files_stay_reviewable src/aeat/domain/calculations/registry/test_registry_reviewability.py::test_registry_toml_fragments_stay_reviewable -q`
  - Result: 2 passed in 6.28s.
- `uv run --no-sync python -c "from aeat.domain.calculations.registry import load_modelo_directory; from aeat.core.resources import bundled_path; m=load_modelo_directory(bundled_path('registry','aeat','modelos','200')); r=m.revisions['2024-y-siguientes']; layout=next(x for x in r.export_layouts if x.id=='modelo-200-fichero-boe'); rec=next(x for x in layout.records if x.id=='modelo-200-page-019'); print(m.id, r.id, rec.id, len(rec.fields))"`
  - Result: `200 2024-y-siguientes modelo-200-page-019 245`.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py::test_committed_registry_tree_loads_directory_modelos -q`
  - Result: 1 passed in 29.27s.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py::test_committed_directory_source_inventory_lists_every_revision_fragment_toml -q`
  - Result: 1 passed in 22.38s.

## Shared Worktree Note

An unrelated dirty file was present during this slice and was not included in
the commit:

- `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/records/parameters.toml`

The dirty file is parameter/legal-rate content, not export fragment layout.
