---
tags:
  - '#exec'
  - '#docs-terminology-search'
date: '2026-07-15'
modified: '2026-07-15'
step_id: 'S12'
related:
  - "[[2026-07-13-docs-terminology-search-plan]]"
---

# Ship display_class in the injected Pagefind meta and replace the per-kind base-weight table with the one declared per-class user-first table (facts, modelo, casilla, cli, user docs, technical last), updating kind_base_weight consumers and tests

## Scope

- `dev/docs/pagefind_inject.py`
- `dev/docs/terminology/_unified_record.py`

## Description

- Ship the display class in the injected Pagefind meta: `_meta_for` now calls `derive_display_class(record)` and emits its value as `display_class` alongside kind, tier, title, summary, weight, and segmento. The axis is a lean display/crumb value the renderer reads verbatim; no grounding data is added to the index meta.
- Replace the per-kind base-weight table with one declared per-display-class user-first table: `doc` (general-fact concept cards) leads, then `modelo`, then `casilla`, then `cli`, then `technical` (api / dev-machinery pages) last.
- Derive the legacy per-kind view from the one class table via a kind-to-class projection, so `kind_base_weight` and `normalise_ranking_weight` (retained for the sweep-relevance reweight path that keys on record kind) can never drift from the single declared authority.
- Retarget every unified funnel (`_from_concept`, `_from_casilla`, `_from_cli_command`, `_from_cli_option`) to rank through the display class via `normalise_display_class_weight`.
- Promote the new public symbols (`ResultDisplayClass`, `derive_display_class`, `display_class_base_weight`, `normalise_display_class_weight`) through the terminology package facade, coherent with the existing ranking-API re-exports.
- Update the pre-existing base-weight ordering assertion consumer test to the amended navigation-tier order (casilla now above cli).

## Outcome

- The injected records carry a `display_class` for the shared search controller to render icons and class-scoped styling from, without re-deriving it in the renderer.
- The base-weight authority is one auditable table; the per-kind view is a thin projection of it. The full terminology test folder is green (one hundred eight passed), and full collect-only ran clean immediately before the commit.

## Notes

- This step's D8 amendment reverses the parent ADR's navigation-tier order (previously cli above casilla); the failing pre-D8 consumer assertion was updated in the same change per the step's own consumer-update clause. It is not peer WIP — the test file was clean at the branch head.
