---
tags:
  - '#exec'
  - '#docs-terminology-search'
date: '2026-07-15'
modified: '2026-07-15'
body_hash: 'sha256:8da0dd1ac1b0ab19f4b480fee852dd1450955c85ea5a8feaa806144e6e9f2a16'
step_id: 'S17'
related:
  - "[[2026-07-13-docs-terminology-search-plan]]"
---

# Emit display_class as data-pagefind-meta on the generated and built pages so directory-indexed full-text page hits carry a ranking weight, completing the D8 user-documentation-above-technical ordering for full-text results, gated by a browser assertion that a how-to page outranks an api stub on a mixed query

## Scope

- `docs/conf.py`
- `dev/docs/pagefind_index.py`
- `dev/docs/tests/test_palette_ranking.py`

## Description

- Stamp `data-pagefind-meta="display_class:<class>"` on the generated and built pages at index time in `dev/docs/pagefind_index.py`, reusing the one `derive_display_class` authority so directory-indexed full-text page hits carry the same closed class the injected records use (no JS re-derivation, no duplicated classification).
- Feed that class into the shipped `weight` sort key so a full-text `doc` (user-documentation) page outranks a `technical` (api / dev-machinery) page, completing the D8 full-text ordering split.
- In `docs/_static/cadrumo-docs.js`, key the card/page coarse band on the pass origin (`isCard`) rather than on any per-page heuristic, so a page hit that now carries a class still sits in the full-text band beneath the term/navigation cards while its within-band order follows the shipped class.
- Add the browser gate `test_search_page_fulltext_class_ranking.py::test_fulltext_user_doc_ranks_above_dev_machinery` asserting a how-to page outranks an api stub on a mixed query.

## Outcome

Delivered on commit `71071ddee6`, verified green (`3 passed`): the new full-text how-to-above-api ordering, plus the retained `iva`-leads and casilla-above-cli orderings. D8 is now fully delivered end to end — the injected-card ranking AND the full-text-page ranking both consume the one shipped display-class weight ladder. The disclosed D8 residual from S15 is closed.

## Notes

Sharp subtlety flagged by the implementer and documented inline: the card-vs-page coarse separation depends index-GLOBALLY on at least one weight-sort-keyed record existing (the weight-sorted pass returns only records carrying a `weight` key). Production always satisfies this because the injected concept/casilla/cli records are always present, so full-text pages reliably fall into the lower band. The gate reproduces the invariant deterministically by injecting a single weighted anchor record alongside the full-text pages, so the ordering it asserts matches production rather than a degenerate index with no weighted records.
