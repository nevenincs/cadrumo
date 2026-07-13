---
tags:
  - '#exec'
  - '#docs-lifecycle-tutorials'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S08'
related:
  - "[[2026-07-13-docs-lifecycle-tutorials-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace docs-lifecycle-tutorials with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S08 and 2026-07-13-docs-lifecycle-tutorials-plan placeholders are machine-filled by
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
     The Author docs/how-to/modelo-130.md on the modelo-303 template with live-verified commands and the this-page-covers opening and ## Scope

- `docs/how-to/modelo-130.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Author docs/how-to/modelo-130.md on the modelo-303 template with live-verified commands and the this-page-covers opening

## Scope

- `docs/how-to/modelo-130.md`

## Description

- Author `docs/how-to/modelo-130.md` on the modelo-303 template shape: the
  "This page covers the ..." opening, the complete verified first-quarter
  chain (profile, two ledger rows, create/calculate/verify/export with the
  three first-period zero bindings), the what-it-calculates section keyed to
  the live casilla table, and a dedicated "Each quarter is cumulative"
  section explaining the year-to-date ledger windows and the three
  `previous_filing` carries with the do-not-pass-zeros-later rule.
- Ground against the live surface this session: `aeat app modelo describe
  130` (quarterly, periods 1T-4T, 20 casillas, 8 bindings), `aeat app modelo
  casillas 130 --period 1T` (casilla ids/labels/input kinds quoted), and
  `aeat app modelo bindings list --modelo 130 --year 2026 --period 1T`
  (binding ids and sources quoted verbatim). The command chain is lifted from
  the existing verified tutorial walkthrough.
- Add the `modelo-130` toctree entry to `docs/how-to/index.md` (grid-card
  regrouping rides P05.S15).

## Outcome

The operator-named "How do I file my Modelo 130?" question now has a
dedicated actionable page, cross-linked to the tutorial, the filing spine,
and the future modelo-100 page.

## Notes

The page links to `modelo-100.md`, authored in the next step (P02.S09); the
link is dangling for the span of one commit and is covered by the P05.S16
gate run.
