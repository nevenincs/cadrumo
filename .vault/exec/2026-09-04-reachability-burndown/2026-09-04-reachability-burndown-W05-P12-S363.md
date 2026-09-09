---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:20269db24a8d5df4c424088f816365aecd09460bf50e910887b07386df6a2145'
step_id: 'S363'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the unconsumed flow frontend-capability and intent enums and their self-referential taxonomy tests.

## Scope

- `core flow vocabulary`
- `flow enum and engine tests`
- `exact unused-symbol signal`

## Changes

- `M` `src/cadrumo/core/flows.py`
- `M` `src/cadrumo/core/tests/test_flows_enums.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest -n0 -m "" src/cadrumo/core/tests/test_flows_enums.py src/cadrumo/application/flows/tests -q` -> `pass (141 passed)`
- `verify:` `uv run --no-sync ruff check src/cadrumo/core/flows.py src/cadrumo/core/tests/test_flows_enums.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass (233 unused symbols; down from 235)`
