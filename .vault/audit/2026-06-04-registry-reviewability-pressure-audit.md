---
tags:
  - '#audit'
  - '#registry-reviewability-pressure'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-06-04-registry-reviewability-pressure-plan]]'
---

# `registry-reviewability-pressure` audit: `pressure inventory`

## Purpose

Inventory the remaining committed registry TOML reviewability pressure after
the generic fragmentation contract was verified. This audit does not approve
data edits; it identifies which layout-only changes should be considered next.

## Measured pressure

The current hard reviewability gate is 1,500 lines and 600 characters per TOML
row. The current baseline gate is 1,250 lines and 575 characters per TOML row.

Largest TOML files by line count:

- `123/revisions/2024-y-siguientes/revision.toml`: 1,218 lines, 290 max row chars.
- `303/revisions/2023-y-siguientes/revision.toml`: 1,033 lines, 542 max row chars.
- `303/revisions/2023-y-siguientes/export/0003-export-layout.part-001.toml`: 969 lines, 153 max row chars.
- `303/revisions/2009-y-siguientes/export/0003-export-layout.part-001.toml`: 969 lines, 153 max row chars.
- `200/revisions/2024-y-siguientes/export/0010-modelo-200-page-007.toml`: 954 lines, 431 max row chars.
- `200/revisions/2024-y-siguientes/export/0075-modelo-200-page-053.toml`: 940 lines, 431 max row chars.
- `123/revisions/2019-2023/revision.toml`: 932 lines, 305 max row chars.

Widest TOML rows:

- `100/revisions/2025/casillas/0618-0552.toml`: 572 characters, 10 lines.
- `100/revisions/2021/completeness/0001-manifest.toml`: 552 characters, 21 lines.
- `100/revisions/2022/completeness/0001-manifest.toml`: 552 characters, 21 lines.
- `100/revisions/2023/completeness/0001-manifest.toml`: 552 characters, 21 lines.
- `100/revisions/2024/completeness/0001-manifest.toml`: 552 characters, 21 lines.
- `202/revisions/2025-y-siguientes/constructs/0001-modelo-202-foundation.toml`: 552 characters, 14 lines.
- `100/revisions/2025/casillas/0616-0550.toml`: 550 characters, 10 lines.
- `303/revisions/2023-y-siguientes/revision.toml`: 542 characters, 1,033 lines.

## Modelo-specific inventory

M100 is already deeply fragmented: six revisions, each represented as a
fragment-directory revision with thousands of small TOML fragments. Its
remaining pressure is row width, not file size.

M123 has two revision directories:

- `123/revisions/2019-2023/revision.toml`: 932 lines, 305 max row chars.
- `123/revisions/2024-y-siguientes/revision.toml`: 1,218 lines, 290 max row chars.

Both M123 revisions also have a separate `completeness-manifest.toml`, but the
main `revision.toml` files carry casillas, formulas, export layouts,
extraction profiles, live cross references, workbook parity refs, verification
expectations, constructs, application links, and deadline windows inline.

M200 is already heavily fragmented: one revision with 1,188 TOML fragments. Its
largest observed file is 954 lines.

M303 has two fragmented revision directories. Its revision metadata file is
still large at 1,033 lines for the 2023 revision, and both revisions have
large export fragments at 969 lines. The files remain below baseline but are
worth tracking after M123.

M369 has three revision directories:

- `369/revisions/esquema-exterior/revision.toml`: 370 lines, 206 max row chars.
- `369/revisions/esquema-importacion/revision.toml`: 343 lines, 204 max row chars.
- `369/revisions/esquema-union/revision.toml`: 469 lines, 245 max row chars.

Each M369 revision also has a separate `completeness-manifest.toml`. The main
revision files are inline-only for the remaining revision content, but they are
not currently near the reviewability baseline.

## Initial risk classification

M123 is the immediate reviewability-pressure target. The 2024 revision is 32
lines below the 1,250-line baseline, and both M123 revision files are large
enough that field-level split review would be materially clearer.

M369 is a consistency target, not a pressure target. A split would be
mechanical, but it would create churn without reducing a near-threshold file.
S02 should decide whether to defer M369 until a later consistency pass.

M100 row width cannot be fixed by revision fragmentation alone because the
widest row is in an already small casilla fragment. If S05 tightens row gates,
M100 rows must first be reformatted mechanically without changing TOML values.

## Next step

S02 should authorise or defer M123 and M369 separately. The strongest immediate
path is to split M123 revision content by appendable field groups while proving
`load_modelo_source` returns an equivalent `ModeloDefinition` before and after.
