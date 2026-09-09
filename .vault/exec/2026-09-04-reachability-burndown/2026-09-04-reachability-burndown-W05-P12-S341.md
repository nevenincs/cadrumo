---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:78819515ae7d3c66c007c674a9aa38c95a7784fb4f057c064d28c6e60f2aa1c7'
step_id: 'S341'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Remove the storage-degradation source census while retaining direct canonical exception behavior checks.

## Scope

- `storage degradation error tests and reachability cadence reference`

## Changes

- `M` `src/cadrumo/adapters/persistence/storage/tests/test_storage_degradation_errors_are_canonical.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/adapters/persistence/storage/tests/test_storage_degradation_errors_are_canonical.py` -> `pass`
- `verify:` `uv run --no-sync ruff check src/cadrumo/adapters/persistence/storage/tests/test_storage_degradation_errors_are_canonical.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass`
