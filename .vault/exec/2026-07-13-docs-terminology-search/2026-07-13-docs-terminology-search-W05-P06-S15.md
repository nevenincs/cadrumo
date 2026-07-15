---
tags:
  - '#exec'
  - '#docs-terminology-search'
date: '2026-07-15'
modified: '2026-07-15'
step_id: 'S15'
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
     The S15 and 2026-07-13-docs-terminology-search-plan placeholders are machine-filled by
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
     The Consume the shipped per-class weights in the compose ladder unchanged and extend the Playwright palette-ranking gate with the two new ordering assertions: casilla above cli on a mixed query, and how-to page above api stub on a mixed query and ## Scope

- `docs/_static/cadrumo-docs.js`
- `dev/docs/tests/test_palette_ranking.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Consume the shipped per-class weights in the compose ladder unchanged and extend the Playwright palette-ranking gate with the two new ordering assertions: casilla above cli on a mixed query, and how-to page above api stub on a mixed query

## Scope

- `docs/_static/cadrumo-docs.js`
- `dev/docs/tests/test_palette_ranking.py`

## Description

- Retire the local `KIND_TIER` heuristic (it re-keyed ranking on record kind and ordered cli above casilla, a second authority conflicting with the shipped weight table).
- Rank on the shipped `meta.weight` (the D8 per-class ladder doc 1.0 > modelo 0.9 > casilla 0.8 > cli 0.7): `tierRank = (isCard ? 1 : 0) + weight`, where `isCard` = "carries a shipped display class". Cards form the +1 band above all full-text pages (retained `RankingTier` coarse axis / term-cards-first); the PERF-003 within-band tie-break (`titleMatch` then `relRank`) in `compose` is untouched.
- Add the segmento to the casilla crumb from the shipped `meta.segmento` (D6).
- Extend the Playwright palette-ranking gate: a new browser test injects a casilla and a cli card sharing one query token and asserts the casilla row renders above the cli row, both class icons render, and the segmento reaches the casilla crumb.

## Outcome

PARTIAL. Delivered and gated on commit `9cfb70eac2`: the casilla-above-cli ordering (the first of D8's two new orderings) plus the JS consumption of the single shipped weight table. Gate `test_palette_ranking.py::test_palette_casilla_outranks_cli_and_renders_class_icon` is green, and the pre-existing `iva`-leads assertions stay green on both hosts.

Deferred: the second D8 ordering assertion, "how-to page above api stub on a mixed query". Full-text page hits are Pagefind directory-indexed and carry no `display_class` / `weight` meta, so the doc-above-technical split for full-text results cannot be expressed in JS without the URL re-derivation the ADR forbids (Axis-6 O6b). The clean completion is a Python/build-side emission of `display_class` as `data-pagefind-meta` on the built pages; tracked as a new follow-up step under this phase with a browser verification gate.

## Notes

This step is honestly PARTIAL, not complete: the step checkbox is left unchecked. The casilla-half is done and gated; the full-text-page half is the disclosed D8 residual carried forward as a tracked step.
