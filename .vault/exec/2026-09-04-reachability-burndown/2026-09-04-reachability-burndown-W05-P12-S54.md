---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:c2a6b34fb3ad3213f51187619353b9bd2c722071f52946e7f282f13df11d3a0a'
step_id: 'S54'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

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
