---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - '[[2026-06-02-registry-hardening-next-work-plan]]'
  - '[[2026-06-02-registry-hardening-fragment-headroom-audit]]'
  - '[[2026-05-19-modelo-registry-fragment-architecture-adr]]'
---

# M200 Export Fragment Pressure Audit

## Scope

This audit executes `P01.S07`: audit M200 export fragments near the
reviewability ceiling.

It measures the current M200 export TOML fragments after the M100
completeness-manifest split sequence and identifies whether `P01.S08` can safely
split the largest M200 export fragment without new loader semantics.

## Summary

M200 now owns the largest committed TOML fragment in the modelo corpus:

- `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0028-modelo-200-page-019.part-002.toml`
  at 1618 lines.
- The second largest file is
  `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0065-modelo-200-page-043.toml`
  at 1612 lines.
- M200 export contains 137 TOML files.
- Eleven M200 export fragments are at or above 1200 lines.
- The pressure shape is regular: each high-pressure file declares one
  `export_layouts` item, one `export_layouts.records` item, and a large
  `export_layouts.records.fields` array.

The safe next split is `P01.S08` against
`0028-modelo-200-page-019.part-002.toml`. That file already participates in a
multi-fragment record page where sibling files repeat the same export layout id
and record id, then append fields. The loader has committed coverage for this
merge behavior.

## Threshold Counts

| Threshold | M200 export files at or above threshold |
| ---: | ---: |
| 1600 | 2 |
| 1500 | 4 |
| 1400 | 7 |
| 1300 | 9 |
| 1200 | 11 |
| 1000 | 11 |
| 750 | 74 |
| 600 | 85 |

## High-Pressure Files

| Lines | Fields | Records | Record id | Path |
| ---: | ---: | ---: | --- | --- |
| 1618 | 117 | 1 | `modelo-200-page-019` | `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0028-modelo-200-page-019.part-002.toml` |
| 1612 | 115 | 1 | `modelo-200-page-043` | `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0065-modelo-200-page-043.toml` |
| 1555 | 113 | 1 | `modelo-200-page-001` | `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0002-modelo-200-page-001.toml` |
| 1555 | 111 | 1 | `modelo-200-page-020d` | `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0033-modelo-200-page-020d.toml` |
| 1472 | 105 | 1 | `modelo-200-page-013` | `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0016-modelo-200-page-013.toml` |
| 1472 | 105 | 1 | `modelo-200-page-032` | `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0054-modelo-200-page-032.toml` |
| 1430 | 102 | 1 | `modelo-200-page-012` | `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0015-modelo-200-page-012.toml` |
| 1359 | 97 | 1 | `modelo-200-page-020b` | `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0031-modelo-200-page-020b.toml` |
| 1304 | 93 | 1 | `modelo-200-page-033` | `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0055-modelo-200-page-033.toml` |
| 1287 | 92 | 1 | `modelo-200-page-014b` | `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0018-modelo-200-page-014b.toml` |
| 1234 | 88 | 1 | `modelo-200-page-026g` | `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0047-modelo-200-page-026g.toml` |

## Existing Page-019 Split Pattern

`modelo-200-page-019` already spans four export fragments:

| Lines | Path |
| ---: | --- |
| 887 | `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0028-modelo-200-page-019.part-001.toml` |
| 899 | `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0028-modelo-200-page-019.part-001b.toml` |
| 20 | `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0028-modelo-200-page-019.part-001c.toml` |
| 1618 | `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0028-modelo-200-page-019.part-002.toml` |

The sibling fragments repeat:

- `[[revisions."2024-y-siguientes".export_layouts]]`
- `id = "modelo-200-fichero-boe"`
- `[[revisions."2024-y-siguientes".export_layouts.records]]`
- `id = "modelo-200-page-019"`

Then they append `records.fields` items. `P01.S08` should follow this existing
shape and split `part-002` at a field boundary into two ordered fragments.

## Recommendation For P01.S08

Split only the current largest fragment first:

- source:
  `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/export/0028-modelo-200-page-019.part-002.toml`
- expected replacement shape:
  - one first fragment retaining the layout id, record id, and an initial field
    run;
  - one second fragment repeating only the layout id and record id before
    appending the remaining fields;
  - both fragments named so sorted loader order preserves the original field
    order.

This does not need new loader or schema semantics. It uses the existing
export-layout record-field merge behavior already covered by the directory-mode
loader tests.

## Verification

- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py::test_committed_registry_toml_files_stay_reviewable src/aeat/domain/calculations/registry/test_registry_reviewability.py::test_registry_toml_fragments_stay_reviewable -q`
  - Result: 2 passed in 5.88s.
- `uv run --no-sync pytest src/aeat/domain/calculations/registry/test_loader_directory_mode.py::test_directory_mode_merges_export_record_field_fragments_by_record_id -q`
  - Result: 1 passed in 0.29s.
