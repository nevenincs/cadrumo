---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:938ae2ba4c69533c482219ff1ed343ff0c9d0239ab0af22a98d5d29b644d68eb'
step_id: 'S250'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the test-owned address component vocabulary and its census gate

## Scope

- `Remove the unreachable production constants and self-owning test`
- `correct product prose and the stale disconnected-capability classification`
- `run focused filing gates`
- `remeasure exact reachability`
- `update the cadence reference`
- `and write the Step Record`

## Changes

- `D` `src/cadrumo/core/address_components.py`
- `D` `src/cadrumo/core/tests/test_address_component_vocabulary.py`
- `M` `src/cadrumo/core/filing_producer_key.py`
- `M` `src/cadrumo/application/filing/producer_snapshot.py`
- `M` `.vault/reference/2026-09-02-unreachable-capability-disconnected-capability-inventory-reference.md`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/core/filing_producer_key.py src/cadrumo/application/filing/producer_snapshot.py` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n0 src/cadrumo/application/filing/tests/test_producer_snapshot.py src/cadrumo/application/filing/tests/test_export_semantic_vocabulary.py src/cadrumo/domain/calculations/registry/tests/test_export_semantic_vocabulary.py dev/registry/tests/test_modelo_210_party_key_coverage.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`
