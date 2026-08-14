---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:0bb5c54eb266807c9513146d42cbcd0a7d9bdd0c003ef1b07f566f48e44b20b4'
step_id: 'S28'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Prove detach, cursor replay, duplicate response refusal, cancellation races, deadline races, and restart reconciliation with real journal storage

## Scope

- `src/cadrumo/application/operations/tests/test_supervisor_recovery.py`

## Description

- Add a real encrypted-reference, filesystem-journal, and filesystem-lease recovery proof.
- Prove detach leaves the durable interaction and ordered cursor replay authoritative.
- Prove a consumed response remains single-use across detached supervisor restart.
- Prove expired-owner checkpoint resumption and unknown interruption through real lease reconciliation.

## Outcome

`uv run --no-sync pytest -q -n 0 -m integration src/cadrumo/application/operations/tests/test_supervisor_recovery.py` passed: 4 passed.

S28 remains open and uncommitted for independent Sol review. The offline RAG waiver was used; grounding read the accepted architecture, implementation research, live supervisor and persistence/recovery authority, and targeted duplicate-test inventory.

## Notes

The pre-existing supervisor suite retains its focused cancellation and aggregate-deadline race proofs; this S28 file adds the missing dedicated durable recovery boundary rather than mirroring those S24 controls.
