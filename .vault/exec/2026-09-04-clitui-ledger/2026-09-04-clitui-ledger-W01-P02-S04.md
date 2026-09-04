---
tags:
  - '#exec'
  - '#clitui-ledger'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:e7525fb8478ab7c7200bd0840104f70c5228703a79a558174dbfe0b9c5cc7b6c'
step_id: 'S04'
related:
  - "[[2026-09-04-clitui-ledger-plan]]"
---

# Enumerate every invocable Ledger command endpoint, sub-operation, handler, schema, and adapter ownership annotation

## Scope

- `src/cadrumo/entrypoints/cli/_app_ledger_command_specs.py`

## Changes

- `M` `src/cadrumo/entrypoints/cli/_app_ledger_command_specs.py`
- `M` `.vault/reference/2026-09-04-clitui-ledger-reference.md`
- `A` `.vault/exec/2026-09-04-clitui-ledger/2026-09-04-clitui-ledger-W01-P02-S04.md`
- `M` `.vault/plan/2026-09-04-clitui-ledger-plan.md`
- `M` `.vault/index/clitui-ledger.index.md`
- `verify:` `uv run --no-sync pytest -q -n 0 src/cadrumo/entrypoints/cli/tests/test_command_spec_deferred_targets.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n 0 src/cadrumo/entrypoints/cli/tests/test_command_spec_kernel.py src/cadrumo/entrypoints/cli/tests/test_command_specs.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n 0 src/cadrumo/entrypoints/cli/tests/test_command_graph_consumers.py` -> `pass`

## Notes

The shared branch advanced during S04. Commits `3e642ad9ee` and `8fc40a069f` captured the source projection and initial reference publication before this record could be committed; this step preserves those commits and only corrects the source digest after the shared formatter change.

The approved S04 scope names the production spec module only. No new test file was added; the existing 30 focused graph/spec tests and direct duplicate-invocable refusal exercise passed, while a durable detector test remains for a separately scoped test owner or reviewer to require.
