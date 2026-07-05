---
tags:
  - '#exec'
  - '#modelo-720-prior-year-baseline'
date: '2026-07-05'
modified: '2026-07-05'
step_id: 'S14'
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
     The S14 and 2026-07-05-modelo-720-prior-year-baseline-plan placeholders are machine-filled by
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
     The Return validated M720 row-indexed binding values from the foreign-assets aggregation resolver through the approved carrier and ## Scope

- `src/aeat/application/aggregation/_foreign_assets.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Return validated M720 row-indexed binding values from the foreign-assets aggregation resolver through the approved carrier

## Scope

- `src/aeat/application/aggregation/_foreign_assets.py`

## Description

- Capture the foreign-assets registry row resolver output instead of discarding it after validation.
- Return the validated row map through `CalculationSourceResolution.row_binding_values`.
- Extend resolver tests to prove the mesh carrier equals the registry row-value output and stays empty when a revision declares no foreign-asset source.
- Extend per-modelo M720 parity tests to prove the resolver carries the same row-indexed values as the prior aggregation path.

## Outcome

- The foreign-assets aggregation resolver now emits validated row-indexed M720 binding values through the approved S13 carrier.
- Scalar `binding_values` remains empty for these repeat-record fields, avoiding synthetic scalar ids.
- No new binding source kind, resolver convention, validator convention, or registry grouping was introduced.
- S15 can now project row-indexed mesh values into draft/export replay without needing to call the foreign-assets row resolver independently.

## Notes

- Gates: scoped ruff check passed; scoped bytecode compilation passed; focused sequential pytest passed with 50 tests.
- Concurrent worktree WIP exists outside this step and was not edited or included in this step.
