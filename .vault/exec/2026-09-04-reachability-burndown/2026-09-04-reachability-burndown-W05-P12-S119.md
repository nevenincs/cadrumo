---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:7c256fff09c82920054f51dd61b100d81d37028b683fe233ba240524704ee67d'
step_id: 'S119'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Classify the typed contracts an implementer satisfies structurally, which no import edge can reach

## Scope

- `dev/audit/reachability_classification.toml`

## Changes

- `M` `dev/audit/reachability_classification.toml`
- `verify:` `uv run --no-sync python -m pytest dev/audit/tests -n0` -> `pass`

## Notes

Six of the fifteen unclassified classes share one reason for being dark, and it
is a property of the design rather than a gap: an implementer satisfies them
structurally, so no import edge to them can exist and the scan is correct that
nothing imports them. `ModeloFinding` says so in its own docstring, naming the
protocol it conforms to and noting the engine reads only `severity`.

A first pass at counting this population was wrong in a way worth recording. An
`isupper()` filter reported a hundred unused classes; sixty of those were
SCREAMING_CASE constants. The real split is forty-seven classes, sixty
constants, and two hundred sixty-eight functions, and the ledger already
covered most of the classes.

A text search for consumers was wrong too, in the other direction: `Translation`
appeared to have seven production consumers, all of which were the English word
in prose. Counting importers by parsing imports rather than matching names gave
zero production importers for all fifteen.
