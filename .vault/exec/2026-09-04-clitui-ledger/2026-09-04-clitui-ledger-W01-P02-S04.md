---
tags:
  - '#exec'
  - '#clitui-ledger'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:6f38dd20d874e7911feb06d88273b8de319b31e33bb50e0f32db69368a95fd9f'
step_id: 'S04'
related:
  - "[[2026-09-04-clitui-ledger-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Enumerate every invocable Ledger command endpoint, sub-operation, handler, schema, and adapter ownership annotation

## Scope

- `src/cadrumo/entrypoints/cli/_app_ledger_command_specs.py`

## Changes

- `M` `src/cadrumo/entrypoints/cli/_app_ledger_command_specs.py`
- `M` `.vault/reference/2026-09-04-clitui-ledger-reference.md`
- `A` `.vault/exec/2026-09-04-clitui-ledger/2026-09-04-clitui-ledger-W01-P02-S04.md`
- `M` `.vault/plan/2026-09-04-clitui-ledger-plan.md`
- `M` `.vault/index/clitui-ledger.index.md`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/entrypoints/cli/tests/test_command_spec_deferred_targets.py src/cadrumo/entrypoints/cli/tests/test_command_spec_kernel.py src/cadrumo/entrypoints/cli/tests/test_command_specs.py src/cadrumo/entrypoints/cli/tests/test_command_graph_consumers.py` -> `pass`

## Notes

The shared branch advanced during S04. Commits `3e642ad9ee` and `8fc40a069f` captured the source projection and initial reference publication before this record could be committed; this step preserves those commits and only corrects the source digest after the shared formatter change.
