---
tags:
  - '#exec'
  - '#docs-terminology-search'
date: '2026-07-13'
modified: '2026-07-13'
step_id: 'S02'
related:
  - "[[2026-07-13-docs-terminology-search-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace docs-terminology-search with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S02 and 2026-07-13-docs-terminology-search-plan placeholders are machine-filled by
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
     The Run the held-out golden queries through the shipped relevance mapping with the miss-rate machinery and commit the baseline miss-rate report and ## Scope

- `dev/docs/terminology/_miss_rate.py`
- `.vault/audit/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Run the held-out golden queries through the shipped relevance mapping with the miss-rate machinery and commit the baseline miss-rate report

## Scope

- `dev/docs/terminology/_miss_rate.py`
- `.vault/audit/`

## Description

- Run `evaluate_held_out_miss_rate()` over the shipped relevance mapping
  with an isolated storage root.
- Adjudicate rung 2 at the ADR D3 threshold 0.10.
- Commit the baseline artifact
  `src/cadrumo/_data/terminology/evaluation/miss-rate-baseline.json`.

## Outcome

5 of 5 held-out cases hit; miss-rate 0.0 over the 72-query / 29-concept
compiled mapping; rung-2 decision keep-deferred. Committed in `485ac85614`.

## Notes

Five cases is too thin a denominator for a ten-percent gate; the held-out
set must grow alongside the W03 vocabulary widening.
