---
tags:
  - '#exec'
  - '#modelo-720-prior-year-baseline'
date: '2026-07-05'
modified: '2026-07-05'
step_id: 'S13'
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
     The S13 and 2026-07-05-modelo-720-prior-year-baseline-plan placeholders are machine-filled by
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
     The Add the approved row-indexed M720 carrier to the calculation source resolution envelope and ## Scope

- `src/aeat/application/aggregation/_source_mesh.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Add the approved row-indexed M720 carrier to the calculation source resolution envelope

## Scope

- `src/aeat/application/aggregation/_source_mesh.py`

## Description

- Add `row_binding_values` to `CalculationSourceResolution` as a typed, 1-based `(binding_id, row_index)` carrier for registry row values.
- Validate row indexes and freeze row-binding values deterministically for replay-safe source resolution state.
- Serialize row-binding coordinates as JSON-safe objects instead of tuple keys.
- Merge row-binding values through exclusive and precedence source-resolution paths while detecting duplicate ownership by full row coordinate.
- Extend source-mesh tests for serialization, empty readiness responses, merge carry-through, and duplicate row-coordinate ownership.

## Outcome

- The source mesh can now carry row-indexed M720 binding values without synthetic scalar ids and without overloading detail-row DTOs.
- Merge semantics remain exclusive by resolver-owned coordinate, preserving the existing source-mesh conflict model.
- The change adds no new binding source kind, resolver convention, validator convention, or registry grouping.
- This unlocks the foreign-assets resolver enrollment work in the next row-carrier steps.

## Notes

- Gates: scoped ruff check passed; scoped bytecode compilation passed; scoped source-mesh pytest passed with 24 tests.
- Concurrent worktree WIP exists outside this step and was not edited or included in this step.
