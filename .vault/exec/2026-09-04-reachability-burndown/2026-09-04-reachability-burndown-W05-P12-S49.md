---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:b1a8fa18f4488a4348efecfb03bc7cb860db3a075165375bc39032e91ac65dff'
step_id: 'S49'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Correct an earlier wrong negative about transitive deadness and adjudicate what the corrected scan surfaced: the first attempt reported zero because it treated a module-level import as proof of life, which is exactly how the review-only workspace type looked consumed while its only consumer was a recorded finding; a two-pass scan over audit-reached symbols found three modules whose whole defined surface is findings, and eight symbols referred to only by them, but those eight resolve to a documented re-export boundary rather than dead code, leaving as the real finding the two command-spec projections that module actually defines, both read by the CLI reference and tree generators

## Scope

- `dev/audit/reachability_classification.toml`

## Changes

- `M` `dev/audit/reachability_classification.toml`
- `verify:` `uv run --no-sync pytest dev/audit/tests/test_reachability_classification.py dev/audit/tests/test_classification_taxonomy_invariants.py dev/audit/tests/test_ledger_citations_resolve.py -m "" -n 0 -k "closed_taxonomy or evidence_behind or stopped_reporting or taxonomy or citation or cited"` -> `pass`

## Notes

The corrected transitive scan found no exploitable population, and the reason
is worth keeping. `entrypoints/cli/command_api.py` reads as a wholly-dead
module because it DEFINES only two functions and both are findings; everything
else in its `__all__` is re-exported from the modules that define it, and those
are live. A definition-based "is this module dead" test therefore mislabels
every re-export boundary. The eight symbols it appeared to hold alive are held
by that re-export list, not by dead code.
