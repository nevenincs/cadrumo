---
tags:
  - '#exec'
  - '#fichero-boe-parity-gate'
date: '2026-07-02'
modified: '2026-07-02'
step_id: 'S19'
related:
  - "[[2026-07-01-fichero-boe-parity-gate-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace fichero-boe-parity-gate with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S19 and 2026-07-01-fichero-boe-parity-gate-plan placeholders are machine-filled by
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
     The Extend the modelo-export-mirrors-official-structure rule source to bind the fichero-BOE transport and mandate full-structure mirror-or-panic, then run vaultspec-core sync and ## Scope

- `.vaultspec/rules/rules/modelo-export-mirrors-official-structure.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Extend the modelo-export-mirrors-official-structure rule source to bind the fichero-BOE transport and mandate full-structure mirror-or-panic, then run vaultspec-core sync

## Scope

- `.vaultspec/rules/rules/modelo-export-mirrors-official-structure.md`

## Description

- Extend the `modelo-export-mirrors-official-structure` rule source to bind the fixed-width fichero-BOE transport: a pre-write hard panic on a structurally-thin `.boe`, keyed on value presence (not casilla-id membership, since `build_draft` emits EMPTY rows), scoped to `fixed_width`. Add Good/Bad examples and cite the review-found EMPTY-membership bug and its fix in the Source.
- Run `vaultspec-core sync` to propagate to all four provider copies plus the aggregated `CLAUDE.md`/`AGENTS.md`.

## Outcome

Committed in `25ae394ab` (7 files). Codified only after the gate completed a full implement -> review -> fix -> validate cycle, per the vaultspec-codify discipline (a lesson qualifies after it has held across one execution cycle; here the cycle included the code review that caught the critical EMPTY-membership defect).

## Notes

Edited the `.vaultspec/rules/` source and propagated via sync per aeat-vaultspec-centralisation; the generated provider copies were not hand-edited.
