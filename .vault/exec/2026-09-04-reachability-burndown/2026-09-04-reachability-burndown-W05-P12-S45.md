---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:be13ff2bdd5853d9cf047c1d9c84b0c58517e1d9001f5dc6c45768deb314d809'
step_id: 'S45'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Record the inverse of the campaign's recurring persistence shape: the bucket output-language hint is READ by live production while nothing writes or clears it, and the reader is documented to fail soft, catching every exception and returning None at DEBUG, so the hint file never exists and every caller silently takes the default language; and the profile inventory pair where neither side is wired, since load has no production reference and save's single apparent one is a docstring sentence describing an older path rather than a call

## Scope

- `dev/audit/reachability_classification.toml`

## Changes

- `M` `dev/audit/reachability_classification.toml`
- `verify:` `uv run --no-sync pytest dev/audit/tests/test_reachability_classification.py dev/audit/tests/test_classification_taxonomy_invariants.py dev/audit/tests/test_ledger_citations_resolve.py -m "" -n 0 -k "closed_taxonomy or evidence_behind or stopped_reporting or taxonomy or citation or cited"` -> `pass`

## Notes

A gate over the secure-object namespace registry was investigated for the
recurring provisioned-persistence findings and rejected. Every namespace is
enumerated by `namespace_registry.py`, so "has a consumer" is trivially true;
excluding that enumerator leaves only the four test-fixture namespaces. The
registry cannot distinguish a store that is used from one that is merely
enumerated, so the audit's symbol-level finding remains the only honest signal
and the existing ratchet already carries it.
