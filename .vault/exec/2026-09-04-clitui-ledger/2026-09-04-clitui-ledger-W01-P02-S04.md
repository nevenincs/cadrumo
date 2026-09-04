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
- `M` `src/cadrumo/entrypoints/cli/tests/test_command_specs.py`
- `M` `.vault/reference/2026-09-04-clitui-ledger-reference.md`
- `A` `.vault/exec/2026-09-04-clitui-ledger/2026-09-04-clitui-ledger-W01-P02-S04.md`
- `M` `.vault/plan/2026-09-04-clitui-ledger-plan.md`
- `M` `.vault/index/clitui-ledger.index.md`
- `verify:` `uv run --no-sync pytest -q -n 0 src/cadrumo/entrypoints/cli/tests/test_command_spec_deferred_targets.py src/cadrumo/entrypoints/cli/tests/test_command_spec_kernel.py src/cadrumo/entrypoints/cli/tests/test_command_specs.py src/cadrumo/entrypoints/cli/tests/test_command_graph_consumers.py` -> `37 passed`
- `verify:` `uv run --no-sync ruff format --check src/cadrumo/entrypoints/cli/_app_ledger_command_specs.py src/cadrumo/entrypoints/cli/tests/test_command_specs.py` -> `pass`
- `verify:` `uv run --no-sync ruff check src/cadrumo/entrypoints/cli/_app_ledger_command_specs.py src/cadrumo/entrypoints/cli/tests/test_command_specs.py` -> `pass`
- `verify:` `uv run --no-sync ty check src/cadrumo/entrypoints/cli/_app_ledger_command_specs.py src/cadrumo/entrypoints/cli/tests/test_command_specs.py` -> `pass`

## Notes

The shared branch advanced during S04. Commits `3e642ad9ee` and `8fc40a069f` remain the source-projection and initial-reference traces; this remediation preserves their history and records the post-review source digest in the reference rather than rewriting either commit.

Independent review reopened S04 for durable declaration detectors, the missing bulk-CSV classification mode, auto-split effect/result distinctions, canonical identity validation, formatter conformance, and the overloaded-endpoint reference count. The existing command-spec test home now covers the live projection and non-mutating missing, unknown, duplicate, unavailable, and invalid-identity mutations. G0 remains open: this is only the complete current CLI stream, not a union-denominator attestation.
