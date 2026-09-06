---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:c5e62bbf08dd4e2091973071fc2722186bcf98c3689d3891946f5d9de672128e'
step_id: 'S50'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Record a producer-replaced-by-constant shape the reachability signal cannot see as a missing consumer: the register scoping classifier and the filed period selection row projector are both unreached while their types and the whole downstream projection are live, because both onboarding run construction sites pass the inconclusive enum constant matching the field default and leave the selection rows at their empty tuple default, so the scoping signal is always inconclusive and the operator is always shown no selection rows even though the plumbing that would carry them is complete

## Scope

- `dev/audit/reachability_classification.toml`

## Changes

- `M` `dev/audit/reachability_classification.toml`
- `verify:` `uv run --no-sync pytest dev/audit/tests/test_reachability_classification.py dev/audit/tests/test_classification_taxonomy_invariants.py dev/audit/tests/test_ledger_citations_resolve.py -m "" -n 0 -k "closed_taxonomy or evidence_behind or stopped_reporting or taxonomy or citation or cited"` -> `pass`

## Notes

Both consequences are operator-visible and neither surfaces as a missing
consumer, because the consumer exists and reads a default. The register scoping
signal is always `INCONCLUSIVE`, hardcoded at both run construction sites and
equal to the field default. The filed period selection rows are always empty,
the run field defaulting to `()` with no site filling it. A constant standing in
for a computed value looks identical to a computed value from the type graph.
