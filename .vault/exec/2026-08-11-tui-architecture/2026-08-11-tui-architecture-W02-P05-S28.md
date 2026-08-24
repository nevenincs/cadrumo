---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-14'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:ef63f70bebf75b97f0f79cb2aca5e5d5db686152a737b0d6ea87361c72ed7d42'
step_id: 'S28'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Prove detach, cursor replay, duplicate response refusal, cancellation races, deadline races, and restart reconciliation with real journal storage

## Scope

- `src/cadrumo/application/operations/tests/test_supervisor_recovery.py`

## Description

- Add a real encrypted-reference, filesystem-journal, and filesystem-lease recovery proof.
- Prove detach leaves the durable interaction and ordered cursor replay authoritative, including a fresh observer replaying only an event committed after a saved nonzero cursor.
- Prove a consumed response remains single-use across detached same-owner supervisor reconstruction.
- Prove cooperative cancellation and aggregate-deadline races persist their request, acknowledgement, settling state, and terminal settlement through the real journal.
- Prove expired-owner checkpoint resumption reloads the durable successor and exact takeover lease; prove unknown interruption reloads the reconciliation event and released lease state.

## Outcome

`uv run --no-sync pytest -q -n 0 -m integration src/cadrumo/application/operations/tests/test_supervisor_recovery.py` passed: 6 passed in 3.25 seconds.

`uv run --no-sync ruff check src/cadrumo/application/operations/tests/test_supervisor_recovery.py` passed.

S28 remains open and uncommitted for independent review. The shared plan row was deliberately left unchanged; semantic discovery grounded the accepted architecture, implementation research, live supervisor, real filesystem persistence authority, and targeted test inventory.

## Notes

The S28 module now owns its cancellation and aggregate-deadline race evidence rather than delegating those clauses to S24. The duplicate-response proof is intentionally limited to same-owner supervisor reconstruction; expired-owner takeover remains established only by the reconciliation cases.
