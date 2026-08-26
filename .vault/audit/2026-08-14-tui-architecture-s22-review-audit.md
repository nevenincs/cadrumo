---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-14'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:702d35ec939bb7730747bce65e720ce04faa42161af2228b8600fd08c7482860'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-11-tui-architecture-adr]]"
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

## Remediation re-review

### idempotency-claim-atomicity-closure | low | Retry visibility now derives only from a complete initial journal

`OperationJournal.create` now resolves and persists the idempotency claim under the canonical journal lock as part of the complete initial snapshot; normal `commit` refuses an idempotent first snapshot. `submit` resolves only complete journals before and after lease conflict and releases its exact lease when creation raises or resolves to an existing invocation. Independent real-filesystem execution proved a conflict publishes neither a journal nor phantom replay, then allows one complete invocation and stable replay after the held scope settles. The added adapter test also proves complete-snapshot discovery and the absence of retired standalone claim files. The original idempotency HIGH is closed in production behavior.

### lease-ownership-and-release-closure | low | Exact tokens, takeover, reconciliation, and terminal release now bind one owner

The supervisor captures one token, requires both owner and token on every mutation, refuses a same-owner different-token interaction before consumption, takes over only the exact expired predecessor through lease compare-and-swap, and releases the exact lease after terminal commit. Independent real-filesystem execution proved token mismatch refusal, expired-owner `INTERRUPTED` settlement, absent released lease state, and immediate acquisition by a replacement operation in the same definition-subject scope. The original lease ownership, reconciliation, and terminal-release HIGH is closed.

### event-free-transition-history-closure | low | Cancellation revisions may advance without inventing events

Journal history now permits nondecreasing event revisions below the current snapshot revision and treats an empty current event batch as a valid event-free transition while preserving the cursor. Independent execution persisted `CANCELLATION_REQUESTED` without an event and then committed and replayed the later terminal event with revisions 1 and 3. The original event-free transition HIGH is closed.

### consumed-interaction-cas-closure | low | The full consumed checkpoint prefix is append-only

The journal now compares complete `OperationConsumedInteraction` objects rather than their IDs. Independent real-filesystem mutation of a consumed response digest was refused without advancing the journal; the focused adapter test plants both digest and consumption-time rewrites. The original consumed-evidence HIGH is closed.

### settlement-definition-boundary-closure | low | Terminal effects are refused before cleanup or persistence

`settle` now resolves the registered definition and rejects an effect outside `permitted_effects` before lease resolution, cleanup, or journal mutation. Independent real-filesystem execution confirmed `UPDATED` is refused for a `NONE`-only definition while the running snapshot remains unchanged. The original settlement-boundary HIGH is closed.

### lease-renewal-supervision | high | A live supervisor cannot renew its lease and loses settlement authority when duration elapses

The persistence lease adapter supports exact renewal, but `OperationSupervisor` never calls its compare-and-swap renewal path. Its token is fixed for the supervisor lifetime and `_require_owned_lease` only accepts an already-active lease. With the production supervisor, journal, lease repository, and secure operand repository on real temporary storage, a one-minute lease was allowed to expire while the original supervisor remained live; its subsequent terminal settlement was refused as `operation is not owned by this supervisor`. A replacement supervisor can later take over and classify interruption, but that does not make the original long-running executor renewable and cannot prevent it from continuing domain work after its authority silently expires. This violates the ADR's renewable-owner lease requirement and leaves the durable long-running vertical slice unable to outlive its configured lease window.

### real-behavior-sensitivity-recheck | medium | One new rollback test never reaches its claimed branch and await remains unproved

The remediation adds direct production-adapter cases for the five original HIGH paths, but the new `test_submit_journal_create_refusal_releases_the_exact_lease_for_retry` does not prove journal-create rollback. It creates a 64-hex `.json` directory before submission; `resolve_idempotency` scans that path first and raises `cannot read operation journal` before lease acquisition, so the expected `create already exists` error and `_release_exact_lease` branch are unreachable. Independent execution through an alternate real encrypted-SQL setup reproduced that ordering. The test is also currently masked earlier by the unrelated bucket setup failure. In addition, no test calls `await_terminal`, whose current implementation performs one inspection and immediately raises for a non-terminal operation rather than awaiting settlement. The original real-behavior sensitivity MEDIUM therefore remains open.

### bucket-manifest-shared-tree-regression | low | The normal S22 integration lane is blocked before S22 construction

The current `BucketManifest` model lacks `status`, while bucket manifest serialization still reads `manifest.status.value`. Both the supervisor module and secure-reference integration test fail inside `isolated_runtime_profile` before constructing an operation supervisor or secure-reference repository. This is a current shared-tree setup regression, not an S22 behavioral failure. Excluding the two setup-dependent modules leaves 185 operation and persistence tests green; the two journal modules pass 24 tests, including both uncommitted adapter cases. Independent alternate real encrypted-SQL execution exercised the remediated S22 production paths without changing the shared bucket code.

### remediation-gates | low | Static gates are clean and the reachable behavioral boundary is explicit

Ruff check and format are clean across both operation packages, basedpyright reports zero errors, warnings, or notes, and scoped `git diff --check` is clean. The normal supervisor gate fails only at the documented bucket setup boundary. The canonical audit remains the sole review artifact; no production code, plan state, commit, branch, alternate index, or other worktree was changed by this review.

## Remediation recommendations

- Add supervisor-owned renewal before the exact current lease expires, using compare-and-swap on the held predecessor and persisting or exposing renewal failure before executor authority can become ambiguous. Add a real long-duration proof that events, effects, interaction, and settlement remain authorized only through successfully renewed leases.
- Replace the pre-planted journal directory test with a real-filesystem interleaving that forces journal creation to fail after lease acquisition, then prove exact release and successful retry. The test must establish that the targeted branch was reached rather than infer it from absent lease state.
- Implement and directly exercise genuine `await_terminal` semantics, including a non-terminal-to-terminal transition, or rename/narrow the API if waiting belongs to a later authorized step; an immediate lookup refusal is not an await proof.
- Rerun the exact supervisor and full S22 lanes after the separately owned `BucketManifest.status` inconsistency is repaired.

Remediation verdict: FAIL. One HIGH and one MEDIUM finding remain; the five original HIGH findings are closed and the unrelated bucket setup regression is separately classified.

## Final remediation re-review

### prior-safety-closures-reconfirmed | low | The five original HIGH defects remain closed

The current production sources still bind idempotency visibility to a complete initial journal, require exact owner and token evidence for mutation, permit event-free cancellation revisions, compare the complete consumed-interaction prefix, and refuse definition-forbidden terminal effects before cleanup or persistence. The full real-adapter supervisor module exercises the ownership, cancellation, reconciliation, terminal-release, and definition-bound refusal paths, while the journal module retains the planted consumed-evidence and complete-snapshot idempotency cases. All 205 operation and persistence tests pass, so none of the five previously closed HIGH findings reopened.

### create-refusal-closure | low | The post-acquisition create failure now reaches exact lease release and retry

The corrected non-idempotent regression does not enter claim resolution. It acquires the real conflict-scope lease, reaches `OperationJournal.create`, receives the expected `initial operation journal create already exists` refusal from the pre-existing operation path, observes no current lease afterward, removes the collision, and successfully retries the same operation ID. Independent execution passed this exact real-filesystem branch. The create-refusal portion of the prior MEDIUM is closed.

### await-terminal-semantic-closure | low | Await now observes a real non-terminal-to-terminal transition

`await_terminal` now reloads until the durable snapshot is terminal. Its regression starts the waiter on a created journal, proves the task remains pending after one scheduling turn, settles through the production supervisor, and receives the terminal journal snapshot. Independent execution passed this behavior. The prior immediate-refusal and missing-sensitivity portion is closed.

### lease-renewal-supervision-final | high | Mutation-triggered extension still cannot keep a quiet long-running executor authoritative

`_require_owned_lease` now extends an exact live predecessor by compare-and-swap, preserves the original acquisition evidence, and refuses owner loss without changing the journal or lease bytes. That closes token-safe renewal for operations which mutate before expiry. It is not supervisor-owned renewal for a quiet executor, however: no scheduled renewal or heartbeat runs while `start` awaits executor work. Independent real-adapter execution submitted and started under a one-minute lease at the acquisition instant, performed no intermediate checkpoint, advanced the supervisor clock to 61 seconds, and attempted valid terminal settlement. Production refused with `operation exact lease expired before renewal`. A legitimate long-running executor can therefore lose authority solely because it emitted no intermediate event, while its domain work may continue. The original lease-renewal HIGH remains open.

### await-terminal-busy-poll | medium | Durable waiting loops without delay or change notification

The semantic await fix performs `journal.load` followed by `asyncio.sleep(0)` until settlement. `sleep(0)` yields but imposes no polling interval, backoff, or repository change notification, so every pending CLI or TUI waiter can repeatedly read and parse the durable journal as fast as the event loop and filesystem permit. The new test settles on the next scheduling turn and cannot detect sustained polling. This is a new production resource-safety and test-sensitivity gap in the real await path.

### final-remediation-gates | low | Behavioral and static gates are clean apart from the reproduced findings

The five focused remediation cases pass, the supervisor module passes all 17 tests, and the complete application-operation plus persistence-operation lane passes all 205 tests. Ruff check and format are clean across both operation packages, basedpyright reports zero errors, warnings, or notes, and scoped `git diff --check` is clean. These gates confirm the exercised behavior but do not cover the quiet-executor expiry or sustained-wait polling cases reproduced above.

## Final remediation recommendations

- Run exact-predecessor renewal independently of executor checkpoints while the supervisor owns a non-terminal operation, stop or quarantine executor authority immediately on renewal failure, and prove a quiet operation can settle beyond multiple lease windows without allowing concurrent takeover.
- Replace zero-delay journal polling with a bounded wait strategy or repository change notification that preserves cancellation and terminal observation semantics. Add a real delayed-settlement test that measures bounded journal reads rather than settling on the next event-loop turn.

Final remediation verdict: FAIL. One HIGH and one MEDIUM finding remain; all other prior findings are closed and no CRITICAL finding was identified.

## Heartbeat and bounded-await re-review

### quiet-executor-heartbeat-closure | low | Independent exact renewal now spans the original lease window

`start` owns and joins the executor task while a separate supervisor loop renews at one third of the configured duration. Renewal and every journal mutation use the same per-operation lock and exact held-predecessor compare-and-swap. The real-storage quiet-executor proof crosses the original lease expiry, refuses a contender while the renewed lease remains live, joins the executor, and settles successfully. The owner-loss proof replaces the lease, observes renewal refusal, cancels and joins the executor, and preserves both original journal and winner lease bytes. The quiet-executor portion of the lease-renewal HIGH is closed.

### bounded-cross-instance-await-closure | low | Terminal waiting is bounded and the durable journal remains authoritative

`await_terminal` combines local commit notification with durable journal reloads using backoff from 25 to 250 milliseconds. The sustained real-file test observes only one to three journal opens across 130 milliseconds and proves cancellation propagates. An independent two-supervisor reproduction submitted and settled through one instance while another instance waited without receiving its local event; the waiter observed terminal revision 1 through the shared journal within the bounded timeout. The busy-poll MEDIUM is closed, and local notification is only a latency optimization rather than authority.

### settlement-owner-refusal-regression | high | A losing supervisor closes owned resources before proving its exact lease

The heartbeat remediation moved `close_async_resources` before the per-operation lock and `_require_owned_lease_unlocked` call in `settle`. Independent execution used the real supervisor, journal, lease repository, and encrypted operand repository with a declared async resource. After releasing the original lease and acquiring the same conflict scope through a replacement supervisor, the stale owner attempted settlement. Settlement refused because its exact lease no longer matched and both journal and winner lease bytes remained unchanged, but the stale owner's declared resource had already been closed once. Cleanup is a supervisor-owned mutation and cannot run before exact current ownership is established. This reopens the exact-ownership and pre-mutation-refusal HIGH despite the correct heartbeat owner-loss path.

### heartbeat-final-gates | low | New behavior and the wider S22 lane are green

The three focused heartbeat and bounded-await tests pass, the supervisor module passes all 20 tests, and the complete application-operation plus persistence-operation lane passes all 208 tests. Ruff check and format are clean across both operation packages, basedpyright reports zero errors, warnings, or notes, and scoped `git diff --check` is clean. The suite has no owner-loss settlement case with a declared resource, which is why these green gates do not detect the reproduced cleanup-before-lease mutation.

## Heartbeat re-review recommendations

- Serialize exact lease proof, owned-resource cleanup, terminal journal commit, and exact release as one supervisor-local settlement critical section. Refuse owner loss before popping or closing any resource, and add a real-storage regression that asserts zero cleanup calls and byte preservation for a stale owner.

Heartbeat remediation verdict: FAIL. One HIGH finding remains; the independent heartbeat and bounded-await findings are closed, no MEDIUM finding remains, and no CRITICAL finding was identified.

## Settlement-order closure re-review

### settlement-owner-refusal-closure | low | Exact lease proof now precedes every cleanup mutation

`settle` now enters the same per-operation critical section used by renewal and journal mutation, proves the exact current lease, reads the resource collection without removing it, closes the resources, and only then removes the collection and commits terminal state. The real-storage regression replaces the original owner, records journal and winner lease bytes, and proves the stale settlement refuses with zero cleanup calls and unchanged durable evidence; a valid winner then closes its own declared resource exactly once. An independent reproduction additionally proved the stale supervisor retains the identical resource collection after refusal and the valid supervisor removes its collection only after the one successful close. The reopened exact-ownership and pre-mutation-refusal HIGH is closed.

### all-s22-findings-final-closure | low | No prior CRITICAL, HIGH, or MEDIUM finding remains open

The complete current implementation retains atomic complete-journal idempotency, exact token and conflict-scope ownership, event-free cancellation revisions, immutable consumed-interaction evidence, definition-bound effect refusal, exact takeover and release, post-acquisition create rollback, independent quiet-executor heartbeat, owner-loss cancellation and join, bounded cross-instance terminal observation, and lease-before-cleanup settlement ordering. Re-reading the current production epicenter and rerunning every focused real-storage proof found no reopened prior defect.

### settlement-closure-gates | low | Exact and broad S22 gates are green

The four focused settlement, heartbeat, owner-loss, and bounded-await tests pass; the supervisor module passes all 21 tests; and the complete application-operation plus persistence-operation lane passes all 209 tests. Ruff check and format are clean across both operation packages, basedpyright reports zero errors, warnings, or notes, and scoped `git diff --check` is clean. The S22 audit is re-attested and clean. Full-vault validation remains separately blocked by the unrelated unresolved status enum placeholder in the test-harness-sanity successor ADR; that shared-tree document is outside S22 and was not changed by this review.

Settlement-order remediation verdict: PASS. No CRITICAL, HIGH, or MEDIUM S22 finding remains open.
