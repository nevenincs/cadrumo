---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-26'
modified: '2026-05-26'
related:
  - '[[2026-05-26-schema-hardening-m131-fragmentation-plan]]'
  - '[[2026-05-26-schema-hardening-open-edge-closeout-audit]]'
---

# M131 Fragmentation Inventory

Modelo 131 is already in directory-mode layout, but its revisions are still stored
as one file per revision under `revisions/*.toml`. The next split does not need
loader work: the generic directory loader already accepts `revisions/<id>/`
fragment directories with `revision.toml` and nested fragment files.

## Source Baseline

| Revision file | Lines | Largest contiguous section |
| --- | ---: | --- |
| `2019-2023.toml` | 938 | `export_layouts`, 335 lines |
| `2024.toml` | 1,654 | `bindings`, 624 lines |
| `2025.toml` | 1,599 | `bindings`, 582 lines |
| `2026.toml` | 1,746 | `bindings`, 582 lines |

## Section Boundaries

| Revision | Section sequence |
| --- | --- |
| `2019-2023` | `revision`, `parameters`, `casillas`, `formulas`, `workbook_parity_refs`, `export_layouts`, `extraction_profiles`, `verification_expectations`, `live_cross_references`, `casillas`, `bindings`, `formulas`, `constructs`, `application_links`, `completeness_manifest` |
| `2024` | `revision`, `parameters`, `casillas`, `bindings`, `formulas`, `workbook_parity_refs`, `export_layouts`, `extraction_profiles`, `verification_expectations`, `live_cross_references`, `casillas`, `bindings`, `formulas`, `constructs`, `application_links`, `completeness_manifest` |
| `2025` | `revision`, `parameters`, `casillas`, `bindings`, `formulas`, `workbook_parity_refs`, `export_layouts`, `extraction_profiles`, `verification_expectations`, `live_cross_references`, `casillas`, `bindings`, `formulas`, `constructs`, `application_links`, `completeness_manifest` |
| `2026` | `revision`, `parameters`, `casillas`, `bindings`, `formulas`, `extraction_profiles`, `live_cross_references`, `workbook_parity_refs`, `export_layouts`, `verification_expectations`, `casillas`, `bindings`, `formulas`, `constructs`, `application_links`, `deadline_windows`, `completeness_manifest` |

## Split Strategy

Create `revisions/<revision-id>/revision.toml` for each revision's scalar
revision table, then move each contiguous section run into a numbered fragment:
`parameters/0001-parameters.toml`, `casillas/0001-casillas.toml`,
`bindings/0001-bindings.toml`, and so on. Repeated later section runs remain
separate numbered fragments, for example `casillas/0002-casillas.toml`.

This keeps the move mechanical and avoids merging distant TOML blocks. It also
keeps every resulting fragment below the existing 1,750-line fragment ceiling.

## Edge Tracking

EDGE-2026-05-26-005 | NEXT | M131 has secondary casilla, binding, and formula
runs after verification/live-reference/export sections. The split must preserve
their relative order by using numbered fragments rather than coalescing them.

EDGE-2026-05-26-006 | WATCH | M131 2026 adds `deadline_windows`; the generic
fragment split must include that section without introducing a deadline-specific
or modelo-specific loader rule.
