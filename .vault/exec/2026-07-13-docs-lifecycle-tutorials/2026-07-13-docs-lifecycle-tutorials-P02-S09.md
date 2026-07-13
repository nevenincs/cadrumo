---
tags:
  - '#exec'
  - '#docs-lifecycle-tutorials'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S09'
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
     The S09 and 2026-07-13-docs-lifecycle-tutorials-plan placeholders are machine-filled by
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
     The Author docs/how-to/modelo-100.md as a condensed how-to cross-linking the Renta deep-dive for mechanism, with live-verified commands including the annual period token and ## Scope

- `docs/how-to/modelo-100.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Author docs/how-to/modelo-100.md as a condensed how-to cross-linking the Renta deep-dive for mechanism, with live-verified commands including the annual period token

## Scope

- `docs/how-to/modelo-100.md`

## Description

- Author `docs/how-to/modelo-100.md` as the condensed annual-Renta how-to:
  the "This page covers the ..." opening, the annual `0A` period token and
  per-year revision resolution, the dependency preflight (`aeat app modelo
  requires 100 --year 2025 --period 0A` and `aeat app modelo work
  dependencies`), the create/calculate/review/verify/export chain, the
  missing-bindings and manual-casilla workflow, and the file/reconcile tail.
  Deep mechanism is delegated to the new Renta explanation document
  (P03.S11) per the ADR.
- Ground against the live surface this session: `aeat app modelo describe
  100` (annual, `0A` only, revisions 2020-2025, 2239 casillas, 63 bindings,
  214 formulas - the annual token re-verified per open question #6),
  `aeat app modelo bindings list --modelo 100 --year 2025 --period 0A`
  (relation_prefill fold-ins from modelos 111/123/130/131/184/190/193,
  previous_filing negative-base carry, profile and renta ledger aggregation
  bindings), `aeat app modelo requires 100 --year 2025 --period 0A` (manual
  casilla inventory), and `aeat app modelo work dependencies --help`.
- Add the `modelo-100` toctree entry to `docs/how-to/index.md`.

## Outcome

The "How do I file my Renta?" question has a dedicated actionable page whose
mechanism depth lives in the companion explanation document.

## Notes

The page links to `../explanation/renta-and-bindings.md`, authored in
P03.S11 immediately after P02.S10; dangling for the span of two commits,
covered by the P05.S16 gate run.
