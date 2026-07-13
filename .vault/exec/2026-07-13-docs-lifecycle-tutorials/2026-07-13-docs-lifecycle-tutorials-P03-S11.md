---
tags:
  - '#exec'
  - '#docs-lifecycle-tutorials'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S11'
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
     The S11 and 2026-07-13-docs-lifecycle-tutorials-plan placeholders are machine-filled by
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
     The Author explanation/renta-and-bindings.md: the labelled deep-dive on how the Renta filing builds from the ledger, the Modelo 130 fold-in, profile facts, registry bindings, cross-period carry, and visible-gaps-not-guessed-zeros and ## Scope

- `ground every command against the live bindings/dependencies/observations surface`
- `docs/explanation/renta-and-bindings.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Author explanation/renta-and-bindings.md: the labelled deep-dive on how the Renta filing builds from the ledger, the Modelo 130 fold-in, profile facts, registry bindings, cross-period carry, and visible-gaps-not-guessed-zeros

## Scope

- `ground every command against the live bindings/dependencies/observations surface`
- `docs/explanation/renta-and-bindings.md`

## Description

- Author `docs/explanation/renta-and-bindings.md` as the sanctioned
  deep-dive: explicitly labelled as the one command-dense explanation page,
  with the "This page covers the ..." opening. Sections: the four source
  kinds (profile facts, ledger aggregations, prior-filing fold-ins, prior
  Renta carry) keyed to the live binding listing; the evidence-gated
  quarterly fold-in with the `work dependencies` preflight and the
  scoped-out-not-silently-skipped rule; the visible-gaps-not-guessed-zeros
  design rule; the cross-year negative-base carry with its revision
  re-confirmation guard; and figure-to-law tracing via `work observations`,
  `work revision`, and per-casilla JSON `legal_refs`/`source_refs`.
- Ground every named command against the live surface this session:
  `bindings list --modelo 100 --year 2025 --period 0A` (profile / ledger /
  relation_prefill / previous_filing sources quoted), `requires 100`,
  `work dependencies --help`, `work observations` (verb existence via the
  operator surface).
- Cross-link the page from `explanation/index.md` (new pointer paragraph
  under "When a form builds on earlier ones" and toctree entry).

## Outcome

The dedicated Renta document the operator mandated exists in the
explanation quadrant, labelled as a deep dive, and is the mechanism
counterpart to the condensed `modelo-100.md` how-to. Phase P03 complete.

## Notes

The IRPF lifecycle tutorial (P04.S12) links here from its annual-close
stage when authored.
