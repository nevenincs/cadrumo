---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:4c2548c6507ba221f3f4db70141922f8ef95042fbf4ce288e555c04f51e76cff'
step_id: 'S91'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace source-casilla-integration with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S91 and 2026-08-22-source-casilla-integration-plan placeholders are machine-filled by
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
     The prove a real worksheet export-pull-calculate encrypted revision round trip and ## Scope

- `src/cadrumo/application/storage/calc_sheets/tests/test_row_set_calculation_roundtrip.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# prove a real worksheet export-pull-calculate encrypted revision round trip

## Scope

- `src/cadrumo/application/aggregation/_foreign_assets.py`
- `src/cadrumo/application/modelo/_calculation_actions.py`
- `src/cadrumo/application/storage/calc_sheets/_styling.py`
- `src/cadrumo/application/storage/calc_sheets/tests/test_row_set_calculation_roundtrip.py`

## Description

- Route S90 `Modelo720RowObservation` values through the existing Modelo 720 source resolver and existing bucket calculation action.
- Retain the registry selector grouping, binding and row coordinates, worksheet source identity, and canonical content fingerprint in the established source-mesh and encrypted revision carriers.
- Guard empty calculation and provenance worksheet bodies so the canonical local exporter remains valid without fabricated rows.
- Exercise the actual XLSX serializer, existing Google pull decoder, S90 ingress boundary, M720 calculation path, and encrypted calculation repository without a mock or network substitute.

## Outcome

The real worksheet round trip retains `per_foreign_asset`, every resolved row-binding coordinate, `detalle:per_foreign_asset:row-1`, and the row fingerprint after encrypted repository read-back. The calculation and persistence route remains the pre-existing M720 resolver, source mesh, and calculation revision repository.

## Notes

The M720 handoff implementation was captured by concurrent shared-worktree commit `2b8164c1ae`; this Step retains that mixed provenance without rewriting history. The scoped follow-on contains the real round-trip regression, empty-export guards, execution record, plan closure, and feature index only.
