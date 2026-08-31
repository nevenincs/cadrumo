---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:38651cfcff5e4c69cb060df52c82311781d3e89a22f5d386437deebc0edec96e'
step_id: 'S89'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# REFUTE the record_design.py five-way decomposition proposed in the sibling Steps, by running the acyclicity check that Step listed as its own prerequisite. The proposal does not survive it. A reference graph over all 141 top-level definitions, counting every Name reference from each definition into another, shows EVERY group pair is bidirectional -- seven cycles, not zero: core<->pdf 14/25, core<->xls 13/11, repair<->core 29/2, repair<->pdf 52/19, pdf<->visual 2/20, xls<->repair 2/2, pdf<->xls 2/1. Cutting the five modules as proposed would create import cycles between them, which the architecture rules reject outright. The size grouping was real and the boundary was not: name vocabulary described what these functions are ABOUT, never what they DEPEND ON, and only the graph could tell the difference. WHAT THE GRAPH ACTUALLY SHOWS. repair<->pdf at 52 and 19 is not a seam but the module's spine -- the repair helpers exist to operate ON pdf row structures, so pdf-extraction at 1106 and row-repair at 1079 are ONE concern of roughly 2185 lines, and the earlier claim that row-repair is the most cohesive extraction candidate is exactly backwards. visual is not a leaf either: it calls pdf 20 times while pdf calls it twice, from _extract_record_design_pdf_stream and _snapshot_pdf_page, so extracting it yields a thin but genuine cycle that only dependency inversion would remove -- design work, not file-splitting. xls is bidirectional with core at 13 and 11. EXACTLY ONE CLEAN CUT EXISTS, and it is small: corrections calls NOTHING -- verified with zero edges into pdf, core, repair or xls -- so it is a pure leaf, freely extractable today at 164 lines across 3 definitions. THE HONEST REVISED EXPECTATION, replacing the sibling Step's projection: that Step said extracting all five groups leaves a core near 1100 lines and plausibly at the 1250 budget. That is withdrawn. Only 164 of 4785 lines are freely extractable, about three percent, and the remaining 4600 are a genuinely entangled parser whose decomposition requires inverting the pdf/repair/visual dependencies rather than moving functions between files. Anyone who splits this module on the name boundary will produce import cycles and have to revert. record_design.py should therefore be treated as REQUIRING DESIGN WORK, not as a mechanical size-budget chore -- and since it cannot be decomposed cheaply, the baseline decision for it is a notes-section acceptance with a stated reason, which is the sanctioned auditable form, rather than a regenerated number

## Scope

- `src/cadrumo/domain/calculations/registry/record_design.py`
- `dev/audit/size_budget_baseline.json`

## Changes

- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P02-S89.md`
- `A` `.vault/audit/2026-08-31-ci-lane-deconflation-p02-s89-execution-self-review-audit.md`

## Notes

- Historical refutation only: the S89 graph invalidated the S84/S85 name-based five-way extraction proposal. It identified corrections as the sole clean leaf and required dependency-inversion design work for the remaining parser; this record makes no claim about a current source split.
- The baseline consequence is historical accepted-rule framing only: a notes-section acceptance was the sanctioned alternative to an unjustified regenerated number. This record neither modifies nor authorizes regeneration, rebaselining, pin deletion, or any source or plan action.
