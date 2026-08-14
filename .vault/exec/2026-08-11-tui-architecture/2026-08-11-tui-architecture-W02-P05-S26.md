---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:698d944fd8655f910e48ece6131afd289b48b253d46cca26a060158401a41bd1'
step_id: 'S26'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Reconcile non-terminal journal entries into resumed, recovered, interrupted, or orphaned states at startup

## Scope

- `src/cadrumo/application/operations/_supervisor.py`
- Canonical operation reconciliation contracts, events, registry, facade, and real integration proofs.

## Description

- Add a closed `OperationReconciliationOutcome` model and ordered `OperationReconciliationEvent` carrying only outcome and opaque lease-transition evidence.
- Require `UNKNOWN` only for durable (`RECORDED` or `RESUMABLE`) owner-loss definitions; preserve the valid ephemeral `{NONE}` capability set. Checkpoint resume remains restricted to a resumable definition, declared interaction kinds, and a resumable executor.
- Validate a persisted checkpoint's interaction kind against the current registered definition before lease takeover, durable resumed event, or executor re-entry. A changed or undeclared kind cannot invoke `resume`; after safe ownership acquisition it settles `INTERRUPTED` with `UNKNOWN`.
- Reconcile a proved expired exact predecessor into one non-overlapping durable outcome: safely recovered unstarted entry, actual resumed checkpoint re-entry, or interrupted unknown-effect terminal settlement.
- Acquire an absent or expired foreign scope only through the existing real lease CAS authority, classify the target durably as orphaned, then settle `INTERRUPTED` with `UNKNOWN` effect. The foreign operation journal remains unchanged and the acquired scope is released.
- Refuse a live owner and propagate corrupt lease reads without journal mutation. No frontend connectivity, process reaping, or broader crash recovery authority was added.

## Outcome

The supervisor is the sole startup-reconciliation authority. It never returns a stale resumable snapshot as if it had restarted work: resumption records the typed resumed outcome and calls the registered resumable executor with the exact persisted, currently-declared interaction checkpoint. All uncertain ownership and cleanup paths settle as `INTERRUPTED` with `UNKNOWN` effect only for durable operations once exclusive authority is established.

Independent final review verdict: PASS. The complete supervisor integration module passed 39 tests and the direct registry module passed 14 tests. Scoped Ruff check, Ruff format check, BasedPyright, and `git diff --check` were clean. Closeout `vault check all` exited 0 with 1,313 shared-corpus warnings, including stale feature-index drift; this is not a broader readiness claim.

## Notes

Semantic RAG was attempted but its shared service could not start because its available interpreter has a CPU-only Torch installation. Grounding therefore used the live `W02.P05.S26` row, ADR D3/D5, architecture research, S17-S25 execution records, full supervisor/journal/lease/registry/execution-context reads, and targeted exact searches for reconciliation and orphan authority.

This S26 scope does not claim frontend connectivity authority, exhaustive crash recovery, or `W07.P16.S96` process reaping.
