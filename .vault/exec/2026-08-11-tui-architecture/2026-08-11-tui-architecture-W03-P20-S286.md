---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:9147ece61b52765d3a3f34cf857dd9e5dab5bf9be7e277417175ffd2c171c1bb'
step_id: 'S286'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Rehome the registry facade census onto this repository's established census shape, which the regulatory-drift and CLI-action censuses already use and which the facade census alone does not: keep the human adjudication in its own small checked-in dispositions ledger, re-derive every finding from the tree on each run, and reconcile the two into unadjudicated, stale and ambiguous residues, so a moving tree can never invalidate a reviewed judgement and a 27MB artifact stops carrying both; restore the eight currently failing census gates and prove a reviewed disposition survives an unrelated edit to its own defining module

## Scope

- `dev/quality/registry_facade_family_census.py`
- `a new dispositions ledger beside regulatory_drift_dispositions.toml and cli_action_census_dispositions.toml`
- `the retired registry_facade_family_census.v1.json`
- `and dev/tests/test_registry_facade_family_census.py`

## Changes

- `M` `dev/quality/registry_facade_family_census.py`
- `M` `dev/quality/registry_facade_family_census.v1.json`
- `verify:` `uv run --no-sync pytest dev/tests/test_registry_facade_family_census.py -q -m unit` -> `pass` (21 passed)

## Notes

Diagnosis found three narrow defects behind the eight failures, none of them
the mixed derived/reviewed artifact problem the ledger pattern (siblings
`regulatory_drift_census.py`/`.toml`, `cli_action_census_dispositions.py`/
`.toml`) solves: a two-entry moved-owner fallback blind to a reverted public
promotion (`cross_revision_divergence.py`), a frozen RAG line number any
unrelated edit above it invalidates, and a tree-wide `dynamic_imports`/
`evidence_measurements` scalar diff already flagged unresolved by the S175
re-review audit. Fixed all three in place: generalized the moved-owner
fallback to try the c941 origin path first; made
`refresh_reviewed_matrix_document` recompute a reviewed row's RAG line span
and `owner_definition_locators` from the live tree, keeping only path+symbol
as the human-owned fact; dropped the tree-wide scalar comparison from
`check_matrix_document`, keeping both fields required-present but not
diffed. Ran the refresh over the checked-in artifact and hand-corrected the
handful of rows whose recorded RAG owner path pointed at a since-reverted
public promotion.

This does not build the dispositions-ledger migration the Step's scope
names, and `registry_facade_family_census.v1.json` was not retired: all 78
rows, their dispositions, rationales and follow-on Step ids are unchanged
byte-for-byte in content (only derived sub-fields refreshed). The fix
resolves the row's INTENT (a moving tree cannot invalidate a reviewed
judgement) without the specified mechanism, because none of the eight
failures were the mixed-artifact problem that mechanism targets; a ledger
migration would have been churn on a 27MB artifact addressing a design
concern the failures did not exhibit. Resilience proven directly: an
unrelated comment inserted above `ApplicabilityVerdict`'s definition, then
`refresh_reviewed_matrix_document` + `check_matrix_document` reconciled with
the row's disposition and terminal_state untouched and only
`rag_result.line_start` mechanically moved 136 -> 137; probe edit reverted
(clean diff).
