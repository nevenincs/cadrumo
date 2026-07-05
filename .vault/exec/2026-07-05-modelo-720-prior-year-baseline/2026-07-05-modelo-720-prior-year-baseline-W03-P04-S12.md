---
tags:
  - '#exec'
  - '#modelo-720-prior-year-baseline'
date: '2026-07-05'
modified: '2026-07-05'
step_id: 'S12'
related:
  - "[[2026-07-05-modelo-720-prior-year-baseline-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace modelo-720-prior-year-baseline with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S12 and 2026-07-05-modelo-720-prior-year-baseline-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Author the M720 row-carrier ADR deciding how row-indexed binding values flow through the source mesh and export draft surfaces and ## Scope

- `.vault/adr/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Author the M720 row-carrier ADR deciding how row-indexed binding values flow through the source mesh and export draft surfaces

## Scope

- `.vault/adr/`

## Description

- Grounded the row-carrier decision with semantic code and vault searches for M720 row-indexed binding values, source mesh carriers, foreign-asset resolver output, and scalar binding ids.
- Confirmed `resolve_foreign_asset_binding_row_values` already returns row values keyed as `(binding_id, row_index)`.
- Confirmed `CalculationSourceResolution.binding_values` is scalar and the current foreign-assets resolver validates the row values but discards them.
- Confirmed `detail_rows` exists in the source mesh but carries domain row DTOs, not registry binding ids plus row indexes.
- Authored `2026-07-05-modelo-720-row-carrier-adr.md` as a proposed row-carrier ADR.

## Outcome

- The ADR chooses a first-class row-indexed binding-value map keyed by the real registry `BindingId` plus a typed 1-based row index.
- The ADR rejects scalar synthetic binding ids and rejects overloading `detail_rows` for M720 binding-value parity.
- The ADR requires merge collision detection by full `(binding_id, row_index)` coordinate and projection to `ModeloBindingValue.row_index` for draft/replay/export.

## Notes

- The vault CLI cannot scaffold two ADRs with the same date and feature stem, so the ADR file uses the unique stem `2026-07-05-modelo-720-row-carrier-adr` while retaining the `modelo-720-prior-year-baseline` feature tag.
- No source code migration was performed in S12; W03.P05 owns the implementation.
