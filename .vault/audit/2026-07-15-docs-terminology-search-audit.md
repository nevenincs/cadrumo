---
tags:
  - '#audit'
  - '#docs-terminology-search'
date: '2026-07-15'
modified: '2026-07-15'
body_hash: 'sha256:1ac24eecb17fe96e9044109b8e02bdd372b063e02cec68383142e3dc6c15705e'
related:
  - "[[2026-07-15-docs-terminology-search-adr]]"
---

# `docs-terminology-search` audit: `D7/D8 controller iconography and re-ranking honesty review`

## Scope

Fresh-context honesty review of the accepted ADR `2026-07-15-docs-terminology-search-adr` (rulings D1-D8) against the shipped code and gates before the campaign is declared structurally complete, per the campaign-close honesty-review discipline. The review reads each ruling as if inherited and asks what is delivered, what is partial, and what is assumed-but-unverified. The JS/controller half (D7/D8, plan phase `W05.P06`) landed on commit `9cfb70eac2`; the Python half (`W05.P05`) on `01a1631353`; the earlier destination/search-page rulings across `W02`-`W04` and the D5 extraction on prior commits.

## Findings

### per-ruling-verdicts | low | D1-D7 delivered; D8 partial (full-text-page split is the disclosed residual)

Per-ruling verdicts. D1 DELIVERED: every shipped record target is renderer-derived (glossary anchor, `cli_reference_page_for_command`, casilla slug authority, built page), with zero query-string record targets. D2 DELIVERED and coordinator-CONFIRMED green: the reviewer marked the kind-agnostic built-site resolvability sweep PLAUSIBLE because they did not pay the expensive full build, but the coordinator ran `test_built_site_resolvability_sweep.py` to completion — `1 passed in 582s` — confirming every projected target resolves to a real page and anchor in the built tree with no query-string targets. D3 and D6 DELIVERED for casilla: the per-modelo generated pages render from the same projection the cards use through one slug authority, and destination grounding-coverage is gated. D4 DELIVERED: CLI targets route through `cli_reference_page_for_command`, the renderer's own routing authority. D5 DELIVERED: one shared search controller drives both the Ctrl-K modal and the inline `search.html`, and the stock PagefindUI drop is retired. D7 DELIVERED: the display class is derived once at the injection seam, shipped in the Pagefind meta, read verbatim by the JS renderer (no re-derivation), and rendered as five licence-clean hand-authored inline-SVG icons. D8 PARTIAL: the single per-display-class weight table plus the JS consumption of it are done, and the casilla-above-cli ordering is delivered and gated; the second ordering (a user-documentation full-text page above an api/dev stub) is unmet because full-text page hits are Pagefind directory-indexed and carry no `display_class`/`weight`, so the split cannot be expressed in JS without the URL heuristic the ADR forbids (Axis-6 O6b). This is the one honest residual of the campaign, carried forward as a tracked step with a verification gate.

### d8-residual-closed | low | D8 now FULLY delivered — full-text page ranking landed

Resolution of the D8 PARTIAL above. The disclosed residual (the user-documentation-above-technical ordering for directory-indexed full-text page hits) has landed on commit `71071ddee6` (plan step `W05.P06.S17`): the build-side index pass stamps `data-pagefind-meta="display_class:<class>"` reusing the one `derive_display_class` authority, so full-text pages now carry the closed class and the shipped weight ladder orders a user-`doc` page above a `technical` (api/dev) page. Gated green by `test_search_page_fulltext_class_ranking.py::test_fulltext_user_doc_ranks_above_dev_machinery` (`3 passed`, alongside the retained `iva`-leads and casilla-above-cli assertions). Subtlety recorded on the S17 exec: the card-vs-page coarse separation depends index-globally on at least one weight-sort-keyed record existing — production always satisfies this via the injected concept/casilla/cli records; the gate injects a weighted anchor to reproduce the production invariant. D8 is delivered end to end; the residual is closed.

### bookkeeping-lag | medium | plan/exec state did not reflect the landed JS work

The JS code landed clean on `9cfb70eac2` but the plan showed `W05.P06` steps unchecked with no execution records, so the operator-facing plan truth lagged the actual state (the pattern the plan-closure-requires-exec-records discipline guards). Actioned in this closure pass: execution records authored for S14/S15/S16, S14 and S16 checked, S15 recorded honestly as partial, and the deferred D8 half tracked as a new step.

### concept-kind-d6-grounding-not-gated | medium | concept destination grounding coverage lacks a parity assertion

The casilla destination has a grounding-coverage parity gate (a record carrying legal_refs whose destination renders none is a failure), but the concept-kind destination-grounding assertion promised by D6 is not yet gated. Being actioned in-campaign by a separate code agent this pass — recorded as actioned, not deferred.

### stale-docstring | low | `_unified_record.py` module docstring names retired per-kind weighting

The `dev/docs/terminology/_unified_record.py` module docstring (lines 14-17) still describes the retired per-kind base-weight framing rather than the per-display-class table. Cosmetic; being corrected in-campaign by a separate code agent — actioned, not deferred.

### stale-cli-regex | low | `test_relevance_data.py` carries the retired query-string casilla-target pattern

The relevance-data target-resolution gate at `dev/docs/terminology/tests/test_relevance_data.py:166` still validates the retired `search.html?q=` casilla-target shape rather than the D3 page+anchor form. Being corrected in-campaign by a separate code agent — actioned, not deferred.

## Recommendations

- Track the D8 full-text-page residual as a real step with a browser verification gate: emit `display_class` as `data-pagefind-meta` on the generated/built pages so directory-indexed full-text hits carry a ranking weight, then assert a how-to page outranks an api stub on a mixed query. Build-now-vs-defer is the operator's call; either way it stays a tracked step. Done in this pass.
- Do not check `W05.P06.S15` as complete: it is honestly partial (casilla-half delivered, full-text-page-half deferred). Done in this pass.
- Close the MEDIUM/LOW items (concept-kind D6 gate, stale docstring, stale CLI regex) via the in-campaign code agent already actioning them; confirm green before declaring the campaign structurally complete.
- The campaign is closeable once this bookkeeping and the deferred-item tracking land: the code verdict is PASS.
