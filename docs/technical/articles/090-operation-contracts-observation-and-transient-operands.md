# Operation contracts, observation and transient operands

[Technical overview](../architecture.md) · [Article index](catalogue.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-090` · **Topic:** [Operations, profiles and workflows](../topics/operations-profiles-and-workflows.md)

<!-- preserved:article -->
**Scope:** 24 files under `src/cadrumo/application/operations`, totaling 5,765 lines, 233,160 bytes and 45,743 measured `o200k_base` proxy tokens. All nine bounded-reader pages were read in order. Static inspection only; no application execution or tests were run.

## Capabilities and mechanisms

Operation definitions carry a complete declaration of durability, replay, baseline, request storage, sensitive input, conflict scope, effects, deadlines, cancellation and owned resources. Validation rejects incompatible combinations: ephemeral work permits only no effect and no durable replay/lease; recorded or resumable work requires a conflict scope; resumable durability must pair with resumable replay; contained cancellation and enforced deadlines require supervisor-owned resources; credential-free journal storage cannot be paired with sensitive input. Named capability profiles make common combinations reusable. Capability contract and cross-axis validation (`src/cadrumo/application/operations/capabilities.py`), operation-definition invariants (`src/cadrumo/application/operations/operation_definition.py`)

The composition layer builds one registry-bound supervisor and renderer-neutral submission, observation, review, result, refresh, cancellation, detach and response services. A submission returns an opaque operation receipt; only a newly admitted invocation receives a process-local response capability, so idempotent replay cannot recreate a lost review bearer. Drain and recovery inventory are exposed through bounded interfaces. Composed service graph (`src/cadrumo/application/operations/composition.py`), submission receipt and response capability (`src/cadrumo/application/operations/composition.py`)

Observation reads an internally consistent snapshot and bounded event page at one event-cursor anchor, then checks that the snapshot's pinned definition digest still matches the current registry. Progress is folded from a compaction checkpoint plus every subsequent event through that anchor. Public projection models validate timeline, lifecycle, cancellation facts, progress bounds, interaction schema identity and terminal references. Event replay requires contiguous rows or an advancing restart cursor; it cannot return events beyond the anchor. Atomic observation and refusal mapping (`src/cadrumo/application/operations/observation.py`), anchored projection contract (`src/cadrumo/application/operations/frontend_projection.py`), event-page continuity checks (`src/cadrumo/application/operations/frontend_requests.py`), journal materialization validation (`src/cadrumo/application/operations/persistence/journal.py`)

The interaction protocol supports digest-bound APPLY/REJECT decisions. A response must match the operation, interaction, revision, continuation, reviewed proposal and response-token digest; APPLY must also match the baseline and proposed-effect digests. A consumed continuation stores the response digest and a proof digest over the original checkpoint, action and time. The persisted form therefore proves which reviewed decision was consumed without retaining the response bearer. Exact response checks (`src/cadrumo/application/operations/interactions.py`), continuation proof (`src/cadrumo/application/operations/interactions.py`)

Transient financial operands have a separate path from credentials and encrypted durable inputs. A definition declares kind, uppercase currency, scale (at most six decimal places), range and a bounded lifetime of at most 30 minutes. The amount itself has no DTO field and is passed only as a call argument into an invocation-scoped in-memory broker. Durable custody records only requirement identity and state. Accepted delivery journals open, bound and delivery-started states before the executor can read the amount; acknowledgement/release uses compare-and-swap. Restart classifies an interruption before delivery as not delivered, after acknowledgement as delivered, and the gap between start and acknowledgement as permanently uncertain. Financial declaration and value bounds (`src/cadrumo/application/operations/financial_operand.py`), custody state and transitions (`src/cadrumo/application/operations/financial_operand_custody.py`), delivery and executor-scoped read (`src/cadrumo/application/operations/financial_operand_submission.py`), restart reconciliation (`src/cadrumo/application/operations/financial_operand_submission.py`), durable custody CAS port (`src/cadrumo/application/operations/persistence/financial_operand_custody.py`)

## Knowledge, security, and implementation assessment

The journal contracts store credential-free snapshots, event batches, idempotency claims, interaction checkpoints and secret requirements. Confidential requests are represented by secure-reference digests rather than inline payload JSON. Snapshots validate identity, revision, terminal receipt, storage policy, secret timing, deadline/cancellation ordering, interaction checkpoints, event ordering and cursor alignment. Journal settlement is a distinct atomic contract that commits the terminal record while releasing the exact conflict lease. These are interface guarantees; this chunk contains protocols, not storage adapters or cryptographic implementation. Persisted snapshot invariants (`src/cadrumo/application/operations/persistence/journal.py`), snapshot/event validation (`src/cadrumo/application/operations/persistence/_journal_snapshot_validation.py`), journal commit and settlement contracts (`src/cadrumo/application/operations/persistence/journal.py`)

Idempotency records hash the caller key together with definition and subject identity, retaining only its digest and exact operation/request references. Error detail is separate from journal prose: registered errors contribute a registered code, message key and scrubbed context, while validation failures contribute record/field/rule facts without the bad value. Context is bounded to 64 entries and 4,096 characters per value; omitted fields are counted. The detail itself is released only as a typed terminal RESULT projection under the current definition contract and schema. Hashed idempotency claim (`src/cadrumo/application/operations/persistence/idempotency.py`), bounded error-detail projection (`src/cadrumo/application/operations/error_detail.py`), authorized settled error-detail read (`src/cadrumo/application/operations/error_detail.py`)

The executor receives narrow runtime capabilities for events, cancellation, deadlines, secure operands, secrets, transient financial operands, cleanup resources and interactions; it does not receive the journal, lease repository or frontend adapters. Definition checks bind the executor factory to the exact request model and require explicit opt-in for credential-free request schemas. Secret and transient-operand definitions cannot resume after owner loss because the runtime cannot recover their in-memory values. Executor context surface (`src/cadrumo/application/operations/owner.py`), definition validation for secret (`src/cadrumo/application/operations/operation_definition.py`), definition validation for transient operands (`src/cadrumo/application/operations/operation_definition.py`)

One concrete consistency gap is visible in the transient-operand expiry path: `expire_lapsed()` removes and clears an in-memory wait, returning an expiry DTO, but does not advance the durable custody checkpoint. If this method is the terminal expiry handler, the repository will continue to report its earlier checkpoint as unsettled until restart reconciliation later classifies it as cancelled. Confirm whether an external caller persists a corresponding transition; absent such a caller, expiry is not durable and does not preserve the declared `EXPIRED` outcome. In-memory expiry sweep (`src/cadrumo/application/operations/financial_operand_submission.py`), durable transition API (`src/cadrumo/application/operations/persistence/financial_operand_custody.py`)

Other limits are unresolved rather than confirmed defects. The source protocols require atomic observation and settlement, but adapter correctness, encrypted storage, lease transactions, repository locking, process containment and downstream authority enforcement must be verified in their implementations. Broad catches in observation and detail resolution produce stable public refusals but rely on separate diagnostics for useful support data. No tests are assigned here, so these guarantees remain statically described and unverified at runtime.

## Dependencies and follow-up

Trace the interfaces to their concrete journal, secure-reference, financial-custody and lease repositories, and inspect supervisor assembly to confirm owner-loss reconciliation is invoked on every process start. Find all callers of `expire_lapsed()` and determine whether they persist an `EXPIRED` checkpoint; otherwise change the local path so it advances durable custody before dropping runtime state. Synthesis should also connect the authority protocol to concrete profile/session enforcement and check the observation service's public consumers.

## Complete assigned-file coverage

All 24 assigned files were read completely through pages 1–9; no portions were unread.

- capabilities.py (`src/cadrumo/application/operations/capabilities.py`)
- composition.py (`src/cadrumo/application/operations/composition.py`)
- drain.py (`src/cadrumo/application/operations/drain.py`)
- error_detail.py (`src/cadrumo/application/operations/error_detail.py`)
- errors.py (`src/cadrumo/application/operations/errors.py`)
- event_replay.py (`src/cadrumo/application/operations/event_replay.py`)
- events.py (`src/cadrumo/application/operations/events.py`)
- financial_operand.py (`src/cadrumo/application/operations/financial_operand.py`)
- financial_operand_custody.py (`src/cadrumo/application/operations/financial_operand_custody.py`)
- financial_operand_submission.py (`src/cadrumo/application/operations/financial_operand_submission.py`)
- frontend_contracts.py (`src/cadrumo/application/operations/frontend_contracts.py`)
- frontend_projection.py (`src/cadrumo/application/operations/frontend_projection.py`)
- frontend_requests.py (`src/cadrumo/application/operations/frontend_requests.py`)
- interactions.py (`src/cadrumo/application/operations/interactions.py`)
- models.py (`src/cadrumo/application/operations/models.py`)
- observation.py (`src/cadrumo/application/operations/observation.py`)
- operation_definition.py (`src/cadrumo/application/operations/operation_definition.py`)
- owner.py (`src/cadrumo/application/operations/owner.py`)
- persistence/__init__.py (`src/cadrumo/application/operations/persistence/__init__.py`)
- persistence/_journal_snapshot_validation.py (`src/cadrumo/application/operations/persistence/_journal_snapshot_validation.py`)
- persistence/events.py (`src/cadrumo/application/operations/persistence/events.py`)
- persistence/financial_operand_custody.py (`src/cadrumo/application/operations/persistence/financial_operand_custody.py`)
- persistence/idempotency.py (`src/cadrumo/application/operations/persistence/idempotency.py`)
- persistence/journal.py (`src/cadrumo/application/operations/persistence/journal.py`)
<!-- /preserved:article -->
