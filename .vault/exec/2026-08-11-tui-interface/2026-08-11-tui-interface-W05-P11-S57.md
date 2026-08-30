---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:0e93d82992535d5562d43bd7c6d674595e9771e17d7df215ff49486a3846a5b1'
step_id: 'S57'
related:
  - "[[2026-08-11-tui-interface-plan]]"
---

# Render the workspace filing destination from what a Workspace admission can actually attest: the two capability rows WITH their producer attribution, the evidence-backed refusals, and the human-handoff facts, with no remote AEAT submission. The view must state the readiness axes are UNMEASURED rather than letting absence imply not-ready. TWO UNMEASURED DISPOSITIONS THAT MUST NOT BE CONFLATED: FILING_DRAFT_READINESS is PERMANENTLY unmeasured in the producer's own words -- the draft builder is pure and stateless, persists nothing, emits no event and stamps no revision field, so there is no producer to read a verdict from, and the module states this is a structural finding rather than a placeholder pending future wiring. FILING_EXPORT_READINESS is genuinely unblockable, pending a ninth contributor port reading the export bucket event that carries the exact revision id. A view that renders both as the same kind of blank misreports one of them. EXCLUDED FROM THIS ROW, and the exclusion is about REACHABILITY not absence: filing history data EXISTS with typed public projections under the operations parent (the filed-history operation module, carrying FiledHistoryPublicResultV1, FiledPeriodSelectionPublicRowV1 and its operation-definition builder) and is NOT reachable from a Workspace admission because no contributor port supplies it -- filed_history appears zero times in the workspace producers module. A future wiring job MUST NOT CONFLATE THE TWO: that projection carries AEAT-sourced FILED history pulled from the sede, which is not the local filing state of a work target

## Scope

- `src/cadrumo/entrypoints/tui/modelo/view/filing.py`

## Changes

- `A` `src/cadrumo/entrypoints/tui/modelo/view/filing.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/entrypoints/tui/modelo/ -m "unit or integration" -n0 -q` -> `pass` (112 passed; the 2 failures are in `src/cadrumo/entrypoints/tui/modelo/view/tests/test_work_review.py`, peer-held and outside this Step)

## Notes

The provenance and filing destinations share one test module, recorded under
`W05.P11.S55`; this Step adds no test module of its own.
