---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:a41000ae717b44ffe60783efe3d12c20c0bb2e95d2ed04bbf746a2f151fbef4f'
step_id: 'S360'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Remove twelve unused command-spec validation and recovery aliases left by the direct-import consolidation.

## Scope

- `CLI command-spec alias surface`
- `command kernel tests`
- `exact unused-symbol signal`

## Changes

- `M` `src/cadrumo/entrypoints/cli/command_spec.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest -n0 -m "" src/cadrumo/entrypoints/cli/tests/test_command_spec_kernel.py -q` -> `pass (14 passed)`
- `verify:` `uv run --no-sync ruff check src/cadrumo/entrypoints/cli/command_spec.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass (250 unused symbols; down from 262)`
