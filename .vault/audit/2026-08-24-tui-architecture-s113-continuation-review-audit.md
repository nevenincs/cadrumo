---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:873660d66b67c1b612024f2a45fd8bd97d420db92e2e174056d30819d7de5715'
related:
  - "[[2026-08-11-tui-architecture-adr]]"
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-24-tui-architecture-censo-operation-authority-reconciliation-research]]"
---

# `tui-architecture` audit: `S113 durable continuation safety review`

## Scope

Audited `W03.P06.S113` against the amended TUI architecture decision, the censo
authority reconciliation research, the execution record, and the complete owned
diff. The review covered secure publication ordering, credential-free journal
state, exact response and intent binding, continuation scheduling, restart
takeover without reacquisition, cancellation and deadline invariants, canonical
ownership, duplication, and real persistence-test integrity.

## Findings

### response-intent-integrity | high | Durable intent is not bound to the persisted response digest

`OperationPendingInteraction.consume` stores `intent` beside a digest of the
original response, but `OperationConsumedInteraction` validates only timestamp
and interaction identity. A credential-free journal document can therefore be
changed from `reject` to `apply`, or conversely, without changing
`response_digest`; strict model hydration accepts the contradictory pair and
`_resume_from_checkpoint` passes it to the effect executor. The digest proves
that some unavailable response existed but cannot prove that the separately
stored continuation intent is the intent that response carried. This violates
the exact single-use continuation requirement at
`src/cadrumo/application/operations/_interactions.py:128` and
`src/cadrumo/application/operations/_interactions.py:179`.

### persistence-gate-regression | high | The canonical real journal suite is red after the consumed-record schema change

The required `intent` and `checkpoint` fields were added to
`OperationConsumedInteraction` without updating the real filesystem journal
immutability regression at
`src/cadrumo/adapters/persistence/operations/tests/test_journal.py:251`. The
focused application-plus-persistence run fails both parametrizations during
fixture construction with missing-field validation errors: 2 failed and 25
passed. The execution record's 50-test claim consequently does not cover the
canonical persistence consumer of the changed durable schema, and the Step
cannot close with the persistence boundary red.

### response-intent-integrity-resolution | high | Resolved: strict hydration recomputes the complete continuation proof

Re-review confirms `OperationPendingInteraction.consume` now derives
`continuation_proof_digest` over interaction identity, intent, response digest,
consumption time, and the complete pending checkpoint. The strict
`OperationConsumedInteraction` validator recomputes that proof during model
hydration and refuses any mismatch before the supervisor can dispatch resume.
The real filesystem-journal regression changes only the persisted intent from
`apply` to `reject` and proves `OperationJournalRepository.load` refuses the
document as invalid. The original HIGH finding is closed.

### persistence-gate-regression-resolution | high | Resolved: canonical fixtures and both operation lanes are green

Re-review confirms the canonical journal fixture now creates the complete
current record through `OperationPendingInteraction.bind` and `consume`, and
its immutable-history matrix covers intent, response digest, consumption time,
checkpoint, and continuation proof. The public executor-protocol fixture also
implements and signature-checks secure `put` and `publish_review`. A sequential
run with all marker filters cleared passed all application and persistence
operation tests: 259 passed. Ruff, BasedPyright, and diff-integrity checks also
passed on the reviewed surface. The original HIGH finding is closed.

## Recommendations

- For `response-intent-integrity`, persist a self-verifying continuation proof
  from which the intent/digest/checkpoint relationship can be recomputed during
  strict hydration, and add an anti-tamper regression that edits only the stored
  intent and proves the real journal load refuses it before executor dispatch.
- For `persistence-gate-regression`, update the existing canonical journal test
  fixture to construct the complete current consumed record and extend its
  immutability parametrization over `intent` and `checkpoint`; rerun the full
  focused application and persistence operation lanes sequentially.
- Do not close `W03.P06.S113` until both HIGH findings are fixed and the formal
  continuation review is rerun.
- Reattestation completed after remediation: both original HIGH findings are
  closed, no CRITICAL or HIGH findings remain open, and `W03.P06.S113` may
  close.
