---
tags:
  - '#exec'
  - '#docs-lifecycle-tutorials'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S14'
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
     The S14 and 2026-07-13-docs-lifecycle-tutorials-plan placeholders are machine-filled by
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
     The Convert tutorials/index.md into a short index introducing the two lifecycle tutorials and the shared persona and ## Scope

- `docs/tutorials/index.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Convert tutorials/index.md into a short index introducing the two lifecycle tutorials and the shared persona

## Scope

- `docs/tutorials/index.md`

## Description

- Rewrite `docs/tutorials/index.md` as the short tutorials index: the "This
  page covers the ..." opening, the shared-persona statement, two grid cards
  (the income-tax year, the IVA year), the tutorials-vs-quickstart
  differentiation sentence, and the toctree for the two lifecycle pages.
  The old single Modelo 130 walkthrough's content was absorbed into
  `irpf-lifecycle.md` stage 2 in P04.S12.
- Retarget `modelo-130.md`'s tutorial link to `irpf-lifecycle.md` and
  update `explanation/index.md`'s two "Tutorial" phrasings to "lifecycle
  tutorials".

## Outcome

Phase P04 complete: the Tutorial quadrant now holds the two chartered
lifecycle lessons behind a thin index, and the old walkthrough survives as
the IRPF tutorial's first-quarter stage rather than as a quickstart
duplicate.

## Notes

`docs/index.md`'s route-grid card still points at `tutorials/index` (valid
link); its card text updates with the landing-grid regroup in P05.S15.
