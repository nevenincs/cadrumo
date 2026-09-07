---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-06'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:a6987a01398b98dedba936f4355ee73fbcda5ca7df7886aecc00ab50e40b044a'
step_id: 'S74'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete two dead duplicates of names that are live elsewhere in the CLI common module: load_transactions(state), whose live namesake is a different function in the review adapters, and a second copy of the operator-surface reconciliation ctx.meta key whose owning module both writes and reads it. The constant-agreement screen reports one name with one value in two modules without judgement, which is right for ordinary repetition and wrong for a meta-key protocol where writer and reader silently stop agreeing the moment one copy is edited.

## Scope

- `src/cadrumo/entrypoints/cli/_common.py`
- `dev/audit/reachability_classification.toml`

## Changes

- `M` `src/cadrumo/entrypoints/cli/_common.py`
- `M` `dev/audit/reachability_classification.toml`
- `verify:` `python -m dev.audit.unreachable_code` unused 1043 -> 1041,
  exact 415 -> 413; neither symbol reported
- `verify:` `python -m dev.quality.unreachable_module_ratchet` exit 0
- `verify:` `ruff check` and `ty check` clean; module imports
- `verify:` ledger validated -- 115 clusters, 273 symbols, no double classification

## Notes

The duplicated `ctx.meta` key is the more interesting of the two. The
constant-agreement screen already sees it and reports one name with one value in
two modules WITHOUT judgement, which is the right default for ordinary
repetition. It is not ordinary for a meta-key protocol: the writer and the reader
agree only while both copies say the same string, and nothing fails when one is
edited. The owning module now holds the only definition.

`load_transactions` was the quieter half of the same shape. A grep for the name
returned the dead CLI copy alongside the live review-adapter function, which
takes different arguments and answers a different question.

Four cases in `test_root_guard_typed_projection.py` fail on this tree. A/B
against `git show HEAD:` of the same file reproduces all four identically, so
they are pre-existing and unrelated -- both deleted symbols had no caller, and
the failures concern requested-leaf binding not clearing between invocations.
