---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:fbee2c1c0237e29d7a711d35e18d51896c00a0d26dabb7448d5756beb0690140'
step_id: 'S48'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace deadline-window-revision-authority with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S48 and 2026-08-24-deadline-window-revision-authority-plan placeholders are machine-filled by
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
     The Restore canonical formatting on the M210 claimed-year design-axis proof introduced by S46, preserving its generalized mutation-bite semantics and ## Scope

- `src/cadrumo/domain/calculations/registry/tests/test_layout_design_applies_to_claimed_years.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Restore canonical formatting on the M210 claimed-year design-axis proof introduced by S46, preserving its generalized mutation-bite semantics

## Scope

- `src/cadrumo/domain/calculations/registry/tests/test_layout_design_applies_to_claimed_years.py`

## Description

- Apply the repository-owned Ruff formatter to the generalized M210 claimed-year design-axis proof introduced by S46.
- Preserve selector operands, ordering, M210/M720 classification, presentation-lag behavior, and mutation-bite semantics.
- Re-run the focused M210, M720, and genuine-violation cases and obtain independent review.

## Outcome

The final diff is exactly three additions and one deletion around the nested `selector_start` conditional. Ruff check and format check pass. Five independently selected M210, M720, presentation-lag, and mutation-bite tests pass. Formal review approved with zero findings.

## Notes

The whole claimed-year inventory remains red for thirteen separately owned modelo design gaps. Neither M210 nor M720 appears in that inventory after S46; those unrelated findings do not alter this formatting-only step.
