---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:ad381f045e5cf6283906df2ff6089c9e962fa3e0678a67cb2624fa7194a7eb63'
step_id: 'S43'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Adjudicate the censo lifecycle routing and the column-level encryption decorators: the registry-owned foundation map resolving Modelo 036 as active and 037 as historical serves a modelo that IS in the registry, yet no production caller reaches it and the whole application censo path contains no reference to 037 or to active-versus-historical routing, so the distinction is declared and never consulted; the two unused AEAD TypeDecorators are not an unencrypted column, since HashedLookup from the same family is live for row-key digests and the sensitive payload path encrypts through the application-layer secure-object envelope instead

## Scope

- `dev/audit/reachability_classification.toml`

## Changes

- `M` `dev/audit/reachability_classification.toml`
- `verify:` `uv run --no-sync pytest dev/audit/tests/test_reachability_classification.py dev/audit/tests/test_classification_taxonomy_invariants.py dev/audit/tests/test_ledger_citations_resolve.py -m "" -n 0 -k "closed_taxonomy or evidence_behind or stopped_reporting or taxonomy or citation or cited"` -> `pass`

## Notes

The censo entry is the one carrying a consequence. Modelo 036 is in the
registry, so this is not a substrate waiting for its modelo: the lifecycle
routing exists, serves a live form, and the application censo path never asks
it whether a form is active or historical.
