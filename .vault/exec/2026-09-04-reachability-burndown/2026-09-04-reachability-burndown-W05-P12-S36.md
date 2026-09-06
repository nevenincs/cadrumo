---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:2e1744d394532e762a139b29acab2d38515d4e1c55cd89a42e399391fab2eb12'
step_id: 'S36'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Stop an undated measurement in the classification ledger from reading as a current one: three tables recorded counts with no date, and the prose beneath exported_unused derived a 4.3 percent proportion from 368 of 8534 declared exports while the live figures had moved to 310 and roughly 8061, so a sentence stated a proportion that no longer held with nothing on the page to warn a reader; date the measurement tables and gate the property, requiring a date rather than currency so that a considered analysis is not turned into churn by every deletion

## Scope

- `dev/audit/tests/test_ledger_measurements_are_dated.py`

## Changes

- `A` `dev/audit/tests/test_ledger_measurements_are_dated.py`
- `M` `dev/audit/reachability_classification.toml`
- `verify:` `uv run --no-sync pytest dev/audit/tests -m ""` -> `pass`

## Notes

The stale counts were dated rather than refreshed. Refreshing the three
top-level totals would have left the per-shape breakdowns beneath them keyed to
the old denominator (`of_total = 368`, `names = 72`), and re-deriving those
needs the shape analysis rerun, which this Step did not do. A consistently
dated snapshot is honest; a half-refreshed one is not.
