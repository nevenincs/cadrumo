---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-08'
body_schema: 'body-v2'
body_hash: 'sha256:6326a17c794618bde63a5f7e04007c8cefa92a000fd20955844bb0c0c5d5d103'
step_id: 'S236'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the broken machine-secret importer filename census and fixed command-identity roster from the command-spec authority test; retain graph-derived projection checks and planted channel/contract refusal proofs.

## Scope

- `Machine-secret command-spec authority tests`
- `accepted production-authored command graph decision`
- `focused gate`
- `cadence reference`
- `and Step Record.`

## Changes

- `M` `src/cadrumo/entrypoints/cli/tests/test_machine_secret_spec_authority.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/entrypoints/cli/tests/test_machine_secret_spec_authority.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n 0 --basetemp .tmp/pytest-s236 src/cadrumo/entrypoints/cli/tests/test_machine_secret_spec_authority.py` -> `pass`
