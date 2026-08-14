---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:348c7432b59cca4c968c2b31d6e0ee754ba66e501540ab2d4b0521067467710f'
step_id: 'S27'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Prove every terminal condition waits for resource cleanup and preserves the truthful effect axis

## Scope

- `src/cadrumo/application/operations/tests/test_supervisor_lifecycle.py`

## Description

- Ground the live `W02.P05.S27` row in ADR decisions D2, D3, and D5; S22-S26 execution evidence and audits; the full supervisor, journal, event, model, cleanup, lease, and real-adapter authorities; and exact lifecycle, effect, cleanup, and settlement test searches.
- Record the explicit offline semantic-RAG waiver and use the named direct-source evidence boundary.
- Add `test_supervisor_lifecycle.py` with real encrypted operands, filesystem journal and lease adapters, and an owned open-file resource whose close observes the durable journal before permitting settlement.
- Exercise `SUCCEEDED`, `REFUSED`, `FAILED`, `CANCELLED`, `TIMED_OUT`, and `INTERRUPTED` with legal independent effect values. Hold each resource close, prove no terminal journal event and no completed `await_terminal` while cleanup is pending, then assert the final typed terminal event and receipt carry the requested effect.
- Refuse terminal persistence when owned cleanup reports an error or exceeds its cleanup window; retain the real journal in its nonterminal state and release the held file resource after the timeout probe.

## Outcome

The new real integration lane passes 8 tests sequentially with `-m integration`. Scoped Ruff, Ruff format, and BasedPyright checks pass. No production defect was exposed, so the S27 change is limited to its dedicated test module and execution evidence.

The plan row remains open and all work is uncommitted for the required independent review. This proof does not claim the later S94/S95 exhaustive resource, process, crash, or reaping coverage.

Independent final S27 review verdict: PASS. The review accepted the bounded real-adapter lifecycle matrix and found no remaining issue within this step's scope.

## Notes

Semantic RAG was explicitly waived because the service was offline. Direct grounding used the live plan row, accepted ADR, S22-S26 execution records and review audits, the complete operation lifecycle authority, adapter reads, and targeted duplicate-census searches.

The initial default pytest invocation collected zero tests because the workspace selector excludes integration markers. The final recorded integration run uses the exact marker and sequential execution. The default worker-topology invocation later blocked before test progress; its exact S27 `uv -> pytest -> Python worker` tree was identified and terminated without touching peer processes. The same real lane completes sequentially, so no timeout suppression, production change, mock, fake, stub, patch, monkeypatch, skip, or xfail was introduced.
