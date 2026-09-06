---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:85ab04c032ac92e4ef40b0cd4e228980da3a5faca21e51ed943ce7ad6fa7c98c'
step_id: 'S54'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Record a measured performance consequence and two filing-runtime dispositions: the locale catalogue's cross-process disk cache is never read or written although its in-process half is live, so every new process pays the roughly 800 millisecond YAML parse the cache was written to avoid according to the measurement in its own module docstring; the default filing profile loader is displaced by the builder that takes an already-resolved taxpayer identity; and the fingerprint cache reset seam is orphaned rather than test support, because the function that would populate the cache is itself unreached and the live schema surface never consults it

## Scope

- `dev/audit/reachability_classification.toml`

## Changes

- `M` `dev/audit/reachability_classification.toml`
- `verify:` `uv run --no-sync pytest dev/audit/tests/test_reachability_classification.py dev/audit/tests/test_classification_taxonomy_invariants.py dev/audit/tests/test_ledger_citations_resolve.py -m "" -n 0 -k "closed_taxonomy or evidence_behind or stopped_reporting or taxonomy or citation or cited"` -> `pass`

## Notes

The locale catalogue cache is the first finding in this campaign with a
quantified cost attached by the code itself: roughly 800 ms of YAML parsing per
process, against single-digit tens of milliseconds for the JSON reload the
cache would serve. The in-process half is live, which is why nothing looked
broken -- `compute_directory_source_digest` is imported and used to build the
cache key, and only the persisted read and write are unreached.
