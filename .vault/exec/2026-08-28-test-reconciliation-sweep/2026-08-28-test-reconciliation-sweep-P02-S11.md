---
tags:
  - '#exec'
  - '#test-reconciliation-sweep'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:484ae3f459a4803f222fe073be6db7e937026231a26ba88ca84c253b8a2e6d6e'
step_id: 'S11'
related:
  - "[[2026-08-28-test-reconciliation-sweep-plan]]"
---

# Derive the ledger public-module set from the package instead of a hand-listed tuple that went stale when a peer relocation published two modules

## Scope

- `src/cadrumo/application/ledger/tests/`

## Changes

- `M` `src/cadrumo/application/ledger/tests/test_public_definition_identity.py`
- `verify:` `pytest src/cadrumo/application/ledger/tests/test_public_definition_identity.py` -> `pass`
