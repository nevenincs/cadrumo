---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-06'
modified: '2026-09-06'
body_schema: 'body-v2'
body_hash: 'sha256:1f87bf9f1ccd8a5984bfd1963d068b972d7f7f7f7a264e20db2f22c83f670f29'
step_id: 'S58'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Reclassify both of the campaign's cost findings after testing them against the live design rather than the finding's own docstring: the locale catalogue disk cache is superseded because locale_map returns a lazy shard catalogue whose full parse runs only from iteration, length and to-dict, none of which production calls, so the eight hundred millisecond figure is not a live cost; and the transcription cache is superseded because the CLI-facing extraction layer states that everything runs on-host in memory, that the evidence bytes, transcription and draft never touch disk, and that the module performs no filesystem write, so persisting a transcription would contradict the live posture rather than complete it

## Scope

- `dev/audit/reachability_classification.toml`

## Changes

- `M` `dev/audit/reachability_classification.toml`
- `verify:` `uv run --no-sync pytest dev/audit/tests/test_reachability_classification.py dev/audit/tests/test_classification_taxonomy_invariants.py dev/audit/tests/test_ledger_citations_resolve.py -m "" -n 0 -k "closed_taxonomy or evidence_behind or stopped_reporting or taxonomy or citation or cited"` -> `pass`

## Notes

Both corrections came from the same missing step: an unreached symbol's own
docstring was taken as the statement of what SHOULD happen, without checking
what the live path says it does. Reading the live consumer reversed both. A
finding's docstring argues for the finding; only the reachable code states the
design in force.

The decision backlog drops from 35 clusters to 33, covering 81 symbols.
