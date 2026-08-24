---
tags:
  - '#research'
  - '#tui-operation-observation'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:4ed819bb83f999eb20476c0c2b889503878c57e31d371e1b214387e520406458'
related:
  - "[[2026-08-11-tui-architecture-adr]]"
  - "[[2026-08-24-tui-registry-api-gate-architecture-reconciliation-audit]]"
---

# `tui-operation-observation` research: `Public operation contract amendment staging`

The accepted TUI architecture already owns operation observation, interaction,
secure operand handling, effect reconciliation, and the canonical TUI plan.
Its live application surface still returns a persistence-oriented snapshot
while progress and replay state remain in a separate event stream. The
unfinished visual cohort therefore has no frontend-safe, atomic contract to
consume. Cross-review also exposed three operation-owned seams that cannot be
delegated to a frontend or Workspace: resolving a safe REVIEW projection,
submitting a transient financial edit operand to one executor, and converting
an operation result into a typed Workspace refresh target. The registry does
not yet publish stable identities for all schemas participating in those seams.

The evidence favors one application-owned, versioned contract set and an
in-place amendment of `2026-08-11-tui-architecture-adr`. A staging ADR may
describe that amendment for review, but cannot be accepted as a sibling owner.
The final decision must delimit atomic observation, review projection,
financial-operand custody, result-to-refresh adaptation, version refusal, and
two exact dependency receipts before the relevant visual cohorts begin.

## Findings

### The accepted TUI architecture is the sole operation-observation authority

The accepted record owns the frontend-neutral envelope and supervisor, the
`entrypoints.tui.operations` projection, the independent lifecycle, terminal
condition, and effect axes, and cursor-based detach/reconnect. It also makes the
modal a projection that holds only operation identity, cursor, latest revision,
pending interaction identity, and render-local state. A new registry or Modelo
record cannot own the same projection without creating a sibling authority.
The reconciliation audit therefore routes this work through an explicit
in-place amendment of that accepted decision. The staging record must be
retained as rejected after adoption so the graph never contains two accepted
owners of the same operation contract. `.vault/adr/2026-08-11-tui-architecture-adr.md:116`,
`.vault/adr/2026-08-11-tui-architecture-adr.md:156`,
`.vault/adr/2026-08-11-tui-architecture-adr.md:175`,
`.vault/adr/2026-08-11-tui-architecture-adr.md:187`,
`.vault/adr/2026-08-11-tui-architecture-adr.md:301`,
`.vault/adr/2026-08-11-tui-architecture-adr.md:328`,
`.vault/adr/2026-08-11-tui-architecture-adr.md:726`,
`.vault/audit/2026-08-24-tui-registry-api-gate-architecture-reconciliation-audit.md:74`.

### The live registry cannot yet identify a complete public contract

`OperationDefinition` binds Python request and result types, phase and
interaction declarations, capabilities, reconciliation, frontend permission,
an optional action reference, and the evolving ephemeral-secret declaration.
It does not bind public request, result, REVIEW projection, response, or
Workspace-refresh schema identities and fingerprints, nor a digest over the
safe public definition. Python module and class identity is not a stable public
schema contract, and the existing generic `OperationReference` does not say
which schema or resolver owns a reference. The ADR must settle a canonical,
registered public-definition manifest without publishing Python or persistence
topology. `src/cadrumo/application/operations/_registry.py:121`,
`src/cadrumo/application/operations/_registry.py:126`,
`src/cadrumo/application/operations/_registry.py:128`,
`src/cadrumo/application/operations/_registry.py:135`,
`src/cadrumo/application/operations/_models.py:42`.

### A REVIEW reference needs a registered safe resolver

The pending interaction stores a presentation code, response-schema reference,
and digests binding its continuation, reviewed proposal, baseline, and proposed
effect. The supervisor securely persists the reviewed operand before exposing
its digest-bound checkpoint. Neither the registry nor the public operation
facade currently declares how a frontend-neutral caller resolves that state to
a safe, versioned review DTO. Returning the encrypted operand or its digest
would expose custody topology; making each frontend understand a domain
reference would invert projection ownership. The evidence favors a pure,
definition-registered projector invoked behind an operation-owned resolver,
with exact schema validation and typed refusal. The ADR must separately settle
observation authority and response bearer authority: rendering a review cannot
grant APPLY or REJECT. `src/cadrumo/application/operations/_interactions.py:25`,
`src/cadrumo/application/operations/_interactions.py:92`,
`src/cadrumo/application/operations/_executor.py:140`,
`src/cadrumo/application/operations/_supervisor.py:1038`,
`src/cadrumo/application/operations/_registry.py:121`.

### Financial edit operands require a distinct transient custody contract

The accepted parent now contains a generic pre-executor secret submission
contract, and the live tree contains an in-flight one-shot byte-buffer broker.
That contract deliberately carries an opaque secret kind and exposes only a
scoped memory view. It does not validate a typed financial edit operand, bind an
edit baseline, establish durable delivery/acknowledgement windows around an
effectful executor, or reconcile a crash after handoff. Conversely,
`OperationSecureOperandLookup` stores confidential operands by canonical digest;
using it for every in-progress editor value would retain a second copy of the
draft before the governed Modelo effect. Operation durability is also a
different axis: a RECORDED operation may consume a transient operand, while an
`EPHEMERAL` operation may not conceal a reconcilable effect.

The evidence favors an operation-owned, definition-declared typed financial
operand handoff that is runtime-only, single-consumer, expiry- and
cancellation-bound, and explicitly reconciled across process-loss windows. The
ADR must settle when durable delivery state is written relative to removal from
memory and executor access, what acknowledgement means, how an authoritative
domain effect receipt narrows `UNKNOWN`, and how non-retention is proven. It
must not weaken the rule that the canonical committed financial value lives
only in encrypted secure storage. `.vault/adr/2026-08-11-tui-architecture-adr.md:221`,
`.vault/adr/2026-08-11-tui-architecture-adr.md:248`,
`.vault/adr/2026-08-11-tui-architecture-adr.md:282`,
`src/cadrumo/application/operations/_secret_submission.py:58`,
`src/cadrumo/application/operations/_secret_submission.py:85`,
`src/cadrumo/application/operations/_executor.py:105`,
`.codex/rules/sensitive-financial-data-secure-storage-only.md:8`.

### An opaque operation result cannot drive a typed Workspace refresh

The terminal receipt carries a generic `result_ref` or `refusal_ref`. Workspace
V1 accepts typed visible or exact Modelo targets and owns a baseline-consistent
read projection. A TUI cannot safely guess that an opaque operation reference
is a Modelo target, nor should generic operations import Modelo request types.
The evidence favors an optional definition-registered, domain-owned pure
adapter invoked through the operation facade. It can validate a terminal result
against the exact operation definition and public contract digest, then return
a safe typed refresh target or refusal. The ADR must keep target derivation in
the domain registration while keeping Workspace assembly and baseline minting
with the Workspace owner. `src/cadrumo/application/operations/_models.py:129`,
`src/cadrumo/application/operations/_models.py:139`,
`.vault/adr/2026-08-24-tui-registry-api-gate-adr.md:153`,
`.vault/adr/2026-08-24-tui-registry-api-gate-adr.md:307`,
`.vault/adr/2026-08-24-tui-registry-api-gate-adr.md:409`.

### Current observation exposes persistence shape rather than a public projection

`OperationSupervisor.inspect`, `observe`, and `detach` return
`OperationPersistedSnapshot` directly. That type carries durable schema version
3, a secure request reference, transition-local events, idempotency state, and
pending and consumed interaction checkpoints. These fields are valid for the
journal and reconciliation boundary but exceed the modal's observation needs
and make storage evolution a frontend change. `OperationSnapshot` is not a
replacement: it retains the concrete request payload and omits deadlines,
cancellation checkpoints, current progress, and pending interaction.
`src/cadrumo/application/operations/_supervisor.py:366`,
`src/cadrumo/application/operations/_supervisor.py:383`,
`src/cadrumo/application/operations/_journal.py:37`,
`src/cadrumo/application/operations/_journal.py:47`,
`src/cadrumo/application/operations/_journal.py:63`,
`src/cadrumo/application/operations/_journal.py:65`,
`src/cadrumo/application/operations/_models.py:151`.

### Snapshot and event state require one atomic observation anchor

The persisted snapshot carries the current envelope revision and event cursor,
but only the events emitted by its latest transition. The persistence record
separately retains complete ordered history and appends the new transition
batch to it. The supervisor currently loads the snapshot and replays history
through separate calls, so a commit between those calls can combine state and
events from different revisions. A frontend-side retry cannot prove which
combination was authoritative.
`src/cadrumo/application/operations/_journal.py:50`,
`src/cadrumo/application/operations/_journal.py:61`,
`src/cadrumo/adapters/persistence/operations/_journal_validation.py:25`,
`src/cadrumo/adapters/persistence/operations/_journal_validation.py:31`,
`src/cadrumo/adapters/persistence/operations/_journal.py:143`,
`src/cadrumo/application/operations/_supervisor.py:369`,
`src/cadrumo/application/operations/_supervisor.py:373`.

The evidence favors an application port that returns the current internal
snapshot and the requested bounded history slice from one persistence read.
The public projector can then bind its envelope revision, anchor cursor,
derived state, and replay page to that exact read. Letting the TUI stitch two
calls is cheaper but reverses projection ownership. Copying all event-derived
state into the durable snapshot would avoid the read join but duplicate event
authority and couple public evolution to the journal schema.

### Progress is an event fold, not a snapshot field

Progress exists only as `OperationProgressEvent(completed, total, unit_code)`;
neither runtime nor persisted snapshots carry a current-progress field.
Consequently the public projection cannot honestly promise progress by merely
renaming the snapshot. It must fold progress events through the observation's
anchor cursor. If retention later compacts history, the application boundary
will need an authoritative fold checkpoint or restart projection; the current
filesystem adapter retains full history and does not yet exercise its modeled
`EXPIRED` or `COMPACTED` replay statuses.
`src/cadrumo/application/operations/_events.py:60`,
`src/cadrumo/application/operations/_models.py:151`,
`src/cadrumo/application/operations/_journal.py:37`,
`src/cadrumo/application/operations/_replay.py:18`,
`src/cadrumo/application/operations/_replay.py:23`,
`src/cadrumo/application/operations/_replay.py:89`,
`src/cadrumo/adapters/persistence/operations/_journal.py:223`.

### Terminal condition must remain explicit and independent

The accepted contract treats lifecycle, terminal condition, and effect as
separate facts. Both snapshot models already validate that terminal condition
is present exactly when lifecycle is terminal and agrees with the receipt.
Any public contract listing lifecycle and effect while reducing terminal
condition to result/refusal or localized terminal copy loses an accepted state
axis and cannot distinguish failed, cancelled, timed-out, and interrupted
settlement. `.vault/adr/2026-08-11-tui-architecture-adr.md:175`,
`src/cadrumo/application/operations/_models.py:160`,
`src/cadrumo/application/operations/_journal.py:52`.

### Replay needs resynchronization semantics as well as a cursor

The application replay model already distinguishes page, caught-up, expired,
compacted, and unknown-operation outcomes and requires expired or compacted
responses to supply an advancing restart cursor. The current adapter produces
only page, caught-up, or unknown-operation because it retains complete history.
A public contract should preserve these dispositions without exposing
`OperationJournalRecord`, and should tell a consumer when to replace its local
fold with the observation anchor instead of silently skipping history.
`src/cadrumo/application/operations/_replay.py:18`,
`src/cadrumo/application/operations/_replay.py:71`,
`src/cadrumo/application/operations/_replay.py:89`,
`src/cadrumo/adapters/persistence/operations/_journal.py:223`.

### Initial interaction observation is narrower than the core enum

The core enum names input, choice, review, apply, and reject families, but the
implemented response union contains only apply and reject responses to a
review checkpoint. The pending durable checkpoint retains only a digest of the
response token; `respond` still requires the raw token. A fresh observer can
therefore see a waiting review but cannot derive response authority from public
state, and the projection must never disclose that token or its digest.
`src/cadrumo/core/operations.py:84`,
`src/cadrumo/application/operations/_interactions.py:25`,
`src/cadrumo/application/operations/_interactions.py:46`,
`src/cadrumo/application/operations/_interactions.py:86`,
`src/cadrumo/application/operations/_interactions.py:98`,
`src/cadrumo/application/operations/_supervisor.py:466`.

The implementable initial surface is review observation with apply/reject
affordances enabled only when the caller separately holds the exact secure
response capability. Input and choice remain unavailable until their response
families and secure submission/custody contract exist. Treating every enum
member as implemented would make the visual plan's current input/choice step a
false capability claim; refusing the whole operation observation would instead
hide lifecycle truth. A typed interaction disposition can preserve observation
while disabling unsupported response paths.

### Public version, envelope revision, and journal schema are distinct axes

The persisted record's `schema_version = 3` governs durable hydration, while
operation revision is the optimistic lifecycle revision and event sequence is
the replay cursor. None is a public observation contract version. A strict
public V1 model alone also cannot return a typed unsupported-version refusal,
because validation fails before version-specific parsing. A minimal version
header followed by exact model dispatch is needed, analogous to the operation
registry's minimal definition header. Pre-release version changes must replace
all in-tree consumers atomically and delete the old public model rather than
introduce read-tolerance. `src/cadrumo/application/operations/_journal.py:47`,
`src/cadrumo/application/operations/_models.py:29`,
`src/cadrumo/application/operations/_registry.py:19`,
`.codex/rules/no-legacy-compatibility.md:8`,
`.codex/rules/no-legacy-compatibility.md:36`.

### Observation and financial-operand cohorts need different receipts

The canonical plan currently asks the TUI controller to call supervisor
inspection directly and the TUI projection to interpret snapshots and
capabilities. It also advertises input and choice interactions before those
response contracts exist. Those steps would crystallize the present leak if
they begin unchanged. The interface campaign already uses machine-readable
dependency receipts, and the reconciliation audit requires receipts to record
source ancestry, public versions, conformance, non-retention proof, and the
cohort opened. `.vault/plan/2026-08-11-tui-architecture-plan.md:177`,
`.vault/plan/2026-08-11-tui-architecture-plan.md:178`,
`.vault/plan/2026-08-11-tui-architecture-plan.md:180`,
`.vault/plan/2026-08-11-tui-architecture-plan.md:184`,
`.vault/adr/2026-08-11-tui-interface-adr.md:184`,
`.vault/audit/2026-08-24-tui-registry-api-gate-architecture-reconciliation-audit.md:163`.

The ADR must settle which public contract set and conformance evidence make
`W05.P11` executable. The plan--not a parallel plan--must then record the exact
C0 artifact
`.vault/reference/2026-08-24-tui-operation-observation-dependency-receipt.md`
as `TuiOperationObservationDependencyReceiptV1`, validated by
`src/cadrumo/application/operations/tests/test_public_operation_dependency_receipt.py`.
Its live-tree gate must verify the accepted parent amendment and rejected
staging record, source ancestry, public definition/schema manifest, atomic
observation, cursor/resynchronization, independent terminal axes, safe REVIEW
resolution, typed result-to-refresh adaptation, forbidden DTO imports, and
secret non-retention.

That evidence cannot honestly prove a future financial edit handoff that does
not exist yet. The operation-side C3 prerequisite therefore needs the separate
artifact
`.vault/reference/2026-08-24-tui-operation-financial-operand-dependency-receipt.md`
as `TuiOperationFinancialOperandDependencyReceiptV1`, validated by
`src/cadrumo/application/operations/tests/test_financial_operand_dependency_receipt.py`.
It must chain the exact C0 receipt digest and prove typed binding,
single-consumer races, delivery/acknowledgement windows, expiry, cancellation,
shutdown, process-loss classification, authoritative effect-receipt narrowing,
Modelo baseline compare-and-swap integration, and raw-value non-retention. It
can open only the operation half of C3; the Workspace/editor decisions and
receipts remain independent prerequisites.

### Alternatives have unequal authority and consistency costs

- Directly expose `OperationPersistedSnapshot`: smallest implementation, but
  publishes storage and checkpoint topology and binds frontends to journal V3.
- Let each frontend join `observe` and `replay`: reuses current calls, but
  creates a race and repeats the authoritative fold in TUI, CLI, and MCP.
- Persist a complete frontend projection: offers one read, but introduces a
  second durable lifecycle record and makes presentation evolution a migration.
- Project one atomic snapshot/event materialization in the application: adds a
  narrow read port and fold, while preserving supervisor, journal, and event
  ownership and giving every frontend one stable contract.
- Accept the staging ADR as a sibling of the existing TUI ADR: makes review
  convenient, but produces two accepted owners for operation observation,
  interaction, and custody.
- Let a frontend resolve review/result references and retain edit operands:
  avoids operation services, but exposes secure-reference meaning, duplicates
  domain adapters, and makes frontend teardown part of effect reconciliation.
- Reuse the generic ephemeral-secret byte broker for financial edits: shares
  memory cleanup mechanics, but lacks typed schema, edit-baseline, durable
  handoff-state, and domain effect-receipt semantics.

The atomic application projection, definition-registered resolver and adapter,
distinct typed financial handoff, and in-place parent amendment best fit the
existing ownership evidence. The ADR must still decide their exact public
models, refusal/version boundaries, adoption transaction, and receipt gates.

### Not investigated

No authenticated browser operation, process cancellation, event compaction,
slow-consumer load test, financial-operand crash injection, or Modelo effect
write was executed. No retention policy beyond the current full-history
filesystem adapter was evaluated. The accepted parent and operation epicentres
were reread at commit `0a6400f216d94ce44847808bef5ab660286ae9c4` while
uncommitted operation-platform work was present in the shared tree. That WIP is
evidence of an evolving dependency, not accepted architecture or a completed
receipt. Implementation and full-suite health remain for the canonical plan.

## Sources

- `.vault/adr/2026-08-11-tui-architecture-adr.md:116`
- `.vault/adr/2026-08-11-tui-architecture-adr.md:156`
- `.vault/adr/2026-08-11-tui-architecture-adr.md:175`
- `.vault/adr/2026-08-11-tui-architecture-adr.md:187`
- `.vault/adr/2026-08-11-tui-architecture-adr.md:221`
- `.vault/adr/2026-08-11-tui-architecture-adr.md:248`
- `.vault/adr/2026-08-11-tui-architecture-adr.md:282`
- `.vault/adr/2026-08-11-tui-architecture-adr.md:301`
- `.vault/adr/2026-08-11-tui-architecture-adr.md:328`
- `.vault/adr/2026-08-11-tui-architecture-adr.md:726`
- `.vault/adr/2026-08-11-tui-interface-adr.md:184`
- `.vault/adr/2026-08-24-tui-registry-api-gate-adr.md:153`
- `.vault/adr/2026-08-24-tui-registry-api-gate-adr.md:307`
- `.vault/adr/2026-08-24-tui-registry-api-gate-adr.md:409`
- `.vault/audit/2026-08-24-tui-registry-api-gate-architecture-reconciliation-audit.md:74`
- `.vault/audit/2026-08-24-tui-registry-api-gate-architecture-reconciliation-audit.md:163`
- `.vault/plan/2026-08-11-tui-architecture-plan.md:177`
- `.vault/plan/2026-08-11-tui-architecture-plan.md:178`
- `.vault/plan/2026-08-11-tui-architecture-plan.md:180`
- `.vault/plan/2026-08-11-tui-architecture-plan.md:184`
- `.codex/rules/no-legacy-compatibility.md:8`
- `.codex/rules/no-legacy-compatibility.md:36`
- `.codex/rules/sensitive-financial-data-secure-storage-only.md:8`
- `src/cadrumo/core/operations.py:84`
- `src/cadrumo/application/operations/_events.py:60`
- `src/cadrumo/application/operations/_interactions.py:25`
- `src/cadrumo/application/operations/_interactions.py:46`
- `src/cadrumo/application/operations/_interactions.py:86`
- `src/cadrumo/application/operations/_interactions.py:98`
- `src/cadrumo/application/operations/_interactions.py:92`
- `src/cadrumo/application/operations/_journal.py:37`
- `src/cadrumo/application/operations/_journal.py:47`
- `src/cadrumo/application/operations/_journal.py:50`
- `src/cadrumo/application/operations/_journal.py:52`
- `src/cadrumo/application/operations/_journal.py:61`
- `src/cadrumo/application/operations/_journal.py:63`
- `src/cadrumo/application/operations/_journal.py:65`
- `src/cadrumo/application/operations/_models.py:29`
- `src/cadrumo/application/operations/_models.py:42`
- `src/cadrumo/application/operations/_models.py:129`
- `src/cadrumo/application/operations/_models.py:139`
- `src/cadrumo/application/operations/_models.py:151`
- `src/cadrumo/application/operations/_models.py:160`
- `src/cadrumo/application/operations/_registry.py:19`
- `src/cadrumo/application/operations/_registry.py:121`
- `src/cadrumo/application/operations/_registry.py:126`
- `src/cadrumo/application/operations/_registry.py:128`
- `src/cadrumo/application/operations/_registry.py:135`
- `src/cadrumo/application/operations/_replay.py:18`
- `src/cadrumo/application/operations/_replay.py:23`
- `src/cadrumo/application/operations/_replay.py:71`
- `src/cadrumo/application/operations/_replay.py:89`
- `src/cadrumo/application/operations/_supervisor.py:366`
- `src/cadrumo/application/operations/_supervisor.py:369`
- `src/cadrumo/application/operations/_supervisor.py:373`
- `src/cadrumo/application/operations/_supervisor.py:383`
- `src/cadrumo/application/operations/_supervisor.py:466`
- `src/cadrumo/application/operations/_supervisor.py:1038`
- `src/cadrumo/application/operations/_executor.py:105`
- `src/cadrumo/application/operations/_executor.py:140`
- `src/cadrumo/application/operations/_secret_submission.py:58`
- `src/cadrumo/application/operations/_secret_submission.py:85`
- `src/cadrumo/adapters/persistence/operations/_journal.py:143`
- `src/cadrumo/adapters/persistence/operations/_journal.py:223`
- `src/cadrumo/adapters/persistence/operations/_journal_validation.py:25`
- `src/cadrumo/adapters/persistence/operations/_journal_validation.py:31`
- commit `0a6400f216d94ce44847808bef5ab660286ae9c4`

