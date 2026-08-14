---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:e1e0559d0978de6402781920cf9e3221ec483cc91d51d04c082b2f5e953735d5'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-11-tui-architecture-adr]]"
  - "[[2026-08-11-tui-architecture-W02-P05-S22]]"
---

# `tui-architecture` audit: `W02.P05.S22 durable supervisor vertical slice`

## Scope

Independent formal review of `W02.P05.S22` against the accepted operation-supervisor architecture, its research and roll-up plan, the S22 execution record, and every current S22 source and test diff. The review freshly grounded the code and vault corpora through live semantic search, read the converged implementation cluster in full, paired the incomplete index with targeted symbol search, and exercised the production journal, lease, and encrypted secure-reference adapters on real temporary storage. No production code was changed.

## Findings

### idempotency-claim-atomicity | high | A failed submit permanently binds its retry key to a nonexistent operation

`OperationSupervisor.submit` persists the idempotency claim in `claim_idempotency` before acquiring the conflict-scope lease and before creating the initial operation journal. Those three actions use separate lock windows. A real-filesystem reproduction first held the same definition-subject scope, then submitted operation `6...6` with a fresh retry key: lease acquisition refused as expected, but retrying the same request returned `6...6` while `OperationJournalRepository.load` reported that operation absent. A crash or commit failure has the same durable orphan-claim window. This violates S22's durable claim under the journal lock and lets a normal conflict poison all later retries without an inspectable operation or recovery state.

### lease-ownership-and-release | high | Tokenless adoption, impossible expired-owner reconciliation, and retained terminal leases break exact ownership

`_require_owned_lease` accepts any active lease whose `owner_id` matches and then copies the durable lease into the new supervisor; it never proves that this instance owns the lease token it was constructed to use or previously acquired. A second supervisor with the same owner ID and a different token successfully consumed the first supervisor's pending interaction. Conversely, `reconcile` observes an expired lease but calls `settle` without an exact takeover, so `_require_owned_lease` refuses and the operation cannot become `INTERRUPTED`. Successful `settle` also never releases the exact lease, causing a subsequent operation in the same definition-subject scope to conflict until expiry. Together these paths contradict exact scope-plus-operation lease evidence, sole-owner mutation, takeover-before-recovery, and prompt conflict-scope release after terminal settlement.

### event-free-transition-history | high | A running cancellation request cannot be durably committed

`request_cancel` advances the snapshot revision without emitting an event, but `_OperationJournalRecord` requires complete history to end at the snapshot revision and additionally rejects an eventful history when the latest snapshot event batch is empty. Through the production supervisor and filesystem repositories, starting a cooperative operation produced revision 1 and event cursor 1; `request_cancel` then failed validation instead of persisting `CANCELLATION_REQUESTED`. The same history law makes any later event skip over an event-free revision illegally. S22 therefore does not implement its request-cancel transition, and the journal's claimed event-free compare-and-swap support is internally contradictory.

### consumed-interaction-cas | high | Journal compare-and-swap permits rewriting already-consumed response evidence

The journal's append-only check compares only the sequence of consumed interaction IDs. It does not compare the immutable `OperationConsumedInteraction` records themselves. A real-filesystem reproduction consumed an exact apply response, constructed the next valid eventful revision with the same interaction ID but a planted response digest, and `OperationJournalRepository.commit` accepted and persisted the replacement digest. Exact single-use evidence is therefore not append-only across compare-and-swap transitions; actor-bound response proof can be rewritten after consumption while every journal revision and lease check remains green.

### settlement-definition-boundary | high | Public settlement can persist an effect forbidden by the operation definition

The executor event context refuses undeclared effects before mutation, but `OperationSupervisor.settle` copies `receipt.effect` directly into the terminal snapshot without consulting the registered definition. A production-adapter reproduction registered an operation permitting only `NONE`, then settled it with `UPDATED`; the journal accepted the undeclared effect. The alternate supervisor mutation path defeats the stated definition-bound pre-mutation guarantee and can publish a terminal effect the executor was prohibited from reporting.

### real-behavior-sensitivity | medium | The green focused suite omits every failing lifecycle and corruption path

The eight supervisor tests cover successful idempotent replay, one live-scope conflict, four undeclared executor calls, and apply/reject consumption. They do not exercise claim rollback or crash windows, lease-token mismatch, lease renewal or release, expired-owner takeover, reconciliation, request-cancel after an event, `await_terminal`, consumed-evidence mutation, or definition-bound settlement. The wider operation and persistence lane passes 193 tests, and Ruff check, Ruff format, and basedpyright are clean, but these direct production-adapter reproductions still fail or accept planted corruption.

## Recommendations

- Make idempotency claim creation and initial journal creation one recoverable atomic protocol under the canonical journal lock. A replay must return an operation only after validating the matching journal; every partial failure must roll back or durably expose a reconcilable state.
- Require the exact held lease, including token, for every mutation. Reconciliation must atomically take over an expired exact predecessor before committing recovery, and terminal settlement must release the exact lease with explicit refusal handling.
- Define journal history so event-free revisions are legal without inventing events: retain the cursor and prior phase, permit revision gaps between adjacent events, and validate the current transition tail independently from complete history.
- Compare the full consumed-interaction prefix, not only interaction IDs, and add planted mutations for response digest and consumption time through the real journal adapter.
- Apply definition capability checks to every supervisor-owned mutation path, including terminal receipt effect, before cleanup or journal mutation.
- Add real-filesystem regression tests for each finding, rerun the exact focused and full operation lanes, and restore the formatting gate before re-review.

Final verdict: FAIL. Five HIGH and one MEDIUM findings remain; no CRITICAL finding was identified.
