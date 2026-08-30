---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:3a9de5faa28b248505e21adcc4745b85097fc4e3442480e7925993d1e4ada24a'
step_id: 'S113'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Rehome the ledger folder-import fold beside the function that produces the per-file results, asserting the invocation-wide fields agree rather than silently taking the first file's

## Scope

- `src/cadrumo/application/ledger/actions_import.py`

## Changes

- `M` `src/cadrumo/application/ledger/actions_import.py`
- `M` `src/cadrumo/entrypoints/cli/_ledger_import_cli.py`
- `verify:` `pytest src/cadrumo/application/ledger/tests -k import -n 0 -m ""` -> `pass` (27)
- `verify:` `pytest src/cadrumo/entrypoints/cli/tests/test_import_directory_ordering.py -n 0 -m ""` -> `pass`

## Notes

The CLI copy took seven fields from the first result without checking the rest
agreed, so a fold of results from different invocations would have reported the
first file's period, bucket and batch id for all of them. The rehomed version
refuses that instead; proved by folding two results differing only in
`bucket_id` and observing the refusal.

One narrowing is carried forward rather than fixed here: `validation` and
`source` are per-file reports and the result model holds one of each, so a
directory import still reports only the first file's. Widening those to tuples
is a model shape change, tracked separately.
