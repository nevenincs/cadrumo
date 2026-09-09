---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:794d9da60f357ddb48d2394a721151c618cf623c9cde64c49670a0ef98fda5ed'
step_id: 'S288'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the test-only workflow declaration-pointer state cluster—persisted field, model, validators, key builder, updater, exports, serialization fixture residue, and dedicated tests—while retaining live filing repositories and encrypted workflow-state behavior; run focused gates, update cadence, and remeasure exact reachability.

## Scope

- `workflow state models and state-persistence tests`

## Changes

- `M` `src/cadrumo/application/workflow/state_models.py`
- `M` `src/cadrumo/application/workflow/tests/test_state_persistence_roundtrip.py`
- `D` `src/cadrumo/application/workflow/tests/test_declaration_key.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` exact search for workflow declaration-pointer vocabulary -> `no relevant production matches`
- `verify:` focused Ruff check -> `pass`
- `verify:` encrypted workflow-state roundtrip tests -> `2 passed`
- `verify:` exact reachability -> `250 unused symbols, 31 unreachable modules, 0 orphaned tests`
