---
tags:
  - '#adr'
  - '#tui-architecture'
date: '2026-08-11'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:398114214e216dc5de9730c44cb0d3f4d20afdb38536ada3aa22bc7340b6b7f8'
related:
  - '[[2026-08-11-tui-architecture-research]]'
  - '[[2026-08-11-tui-interface-research]]'
  - '[[2026-08-11-tui-interface-adr]]'
  - '[[2026-07-23-tui-wizard-substrate-adr]]'
  - '[[2026-08-09-cli-action-envelope-hardening-adr]]'
  - '[[2026-07-24-profile-bundle-tui-adr]]'
  - '[[2026-07-25-censal-profile-autofill-adr]]'
  - '[[2026-08-08-sync-control-surface-adr]]'
  - '[[2026-08-24-tui-architecture-censo-operation-authority-reconciliation-research]]'
  - '[[2026-08-24-tui-architecture-pre-custody-login-secret-submission-research]]'
  - '[[2026-08-24-tui-architecture-pre-custody-login-secret-submission-reference]]'
---

# `tui-architecture` adr: `Application-owned operation envelope and supervisor API` | (**status:** `accepted`)

## Problem Statement

Frontend-triggered application work has no canonical execution boundary. The
TUI owns worker lifetimes, busy state, progress prose, interaction handoff, and
terminal presentation while opaque callbacks independently own effects,
persistence, deadlines, and cleanup. Extending any frontend mechanism would
preserve this split and require each future tool call to reconstruct the same
safety contract.

This record establishes one application-owned operation envelope and
`OperationSupervisor` API. TUI, CLI, and MCP remain projections over that
authority. The defect and option boundary are grounded in
`2026-08-11-tui-architecture-research`; census synchronization is a mandatory
acceptance scenario, not the architecture's scope or vocabulary.

This is the backend architecture required to make a future TUI safe and
expressive. It does not decide the holistic frontend information architecture,
screen hierarchy, navigation model, wizard composition, or final visual
component catalogue. A parallel frontend ADR may decide those concerns, but it
must conform to this record's canonical `cadrumo.entrypoints.tui` placement and
`components` naming rather than create a competing package root.

## Considerations

- Stable action identity, precondition evidence, and recovery references already
  belong to the application action catalogue; this decision must compose them,
  not create a competing catalogue
  (`2026-08-09-cli-action-envelope-hardening-adr`).
- The CLI envelope is a terminal wire projection, not an internal dispatcher
  (`2026-06-10-cli-envelope-notice-standardisation-adr`).
- MCP confirmation and process controls are transport-level defense in depth;
  they cannot manufacture application approval
  (`2026-06-30-agent-harness-adr`).
- Lifecycle position, terminal condition, and committed effect answer different
  questions and must remain independently representable
  (`2026-08-11-tui-architecture-research`).
- Cancellation, deadlines, durability, resumability, and resource ownership are
  capabilities, not promises every executor can honestly make
  (`2026-08-11-tui-architecture-research`).

## Considered options

- **Expand `ManagerAction` and `ManagerActionOutcome`.** Rejected because it
  retains execution authority in Textual and leaves credential, CLI, and MCP
  lifecycles separate.
- **Share events while retaining raw frontend callbacks.** Rejected because it
  improves rendering without owning interaction, cancellation, concurrency,
  cleanup, or settlement.
- **Use the CLI `SchemaEnvelope` as the internal bus.** Rejected because that
  versioned terminal wire contract carries CLI projection concerns and does not
  supervise work.
- **Create independent domain or frontend supervisors.** Rejected because it
  preserves duplicated lifecycle authority.
- **Application-owned operation envelope plus `OperationSupervisor`.** Chosen.
  Domain executors retain policy and effect ownership; one application service
  owns invocation, observation, interaction, cancellation, deadlines, cleanup,
  and settlement; frontends project its typed state.

## Constraints

- Operation execution identity and recovery-action identity are distinct.
  Operation definitions MUST NOT be keyed by `ActionReference`; they may carry
  an optional validated `ActionReference` only when an existing recovery or
  next-action verdict actually dispatches that operation.
- The application envelope MUST contain no localized prose, CLI path, terminal
  formatting, Textual worker identity, transport token, spinner state, or secret
  value.
- Every operation type MUST declare durability, cancellation, deadline,
  idempotency or replay, baseline, sensitive-input, conflict-scope, and owned
  resource capabilities. Omission is invalid, not permissive.
- A terminal condition MUST NOT be published while executor work or resource
  cleanup can still change the effect axis.
- `CANCELLED` and `TIMED_OUT` MUST mean execution stopped and cleanup settled;
  cancelling an observer, wrapper worker, or countdown cannot produce either.
- Secret-bearing interaction values MUST remain within secure custody and MUST
  NOT enter journals, diagnostics, events, approval digests, or projections.
- Unsafe interruption windows MUST declare cancellation unsupported until the
  operation can stop without violating its domain invariants.
- The accepted action identity, wizard-state, and CLI projection contracts are
  stable parents. The supervisor does not depend on evolving MCP SDK hooks.

## Implementation

### D0 - Scope and topology authority

This ADR owns the frontend-neutral operation backend, its persistence and
composition ports, and the narrow
`cadrumo.entrypoints.tui.operations` projection needed to observe and control
that backend. The `tui-interface` concern owns the TUI shell, `components`,
profile, secret, flow, Modelo, testing, navigation, information architecture,
screen grouping, and visual composition. Neither concern may move application
policy into the TUI.

This accepted ADR is the topology authority. The canonical frontend home is
`src/cadrumo/entrypoints/tui/`, with `components`, `operations`, `profile`,
`secret`, `flows`, and reserved `modelo.view` and `modelo.edit`. A top-level
`cadrumo.tui`, a top-level `cadrumo.bootstrap`, nested `entrypoints.tui.core`,
`shared`, and generic `surfaces` packages are prohibited. Related frontend
decisions conform to this tree and do not reopen its root or naming.

### D0a - Existing-capability reuse ledger

The operation platform fills the missing supervision layer and MUST compose,
not redeclare, these existing authorities:

- `cadrumo.application.operator_actions` retains recovery-action identity,
  binding provenance, and action catalogue authority. Operations add a distinct
  definition identity and only an optional join.
- `cadrumo.core.observability` retains run correlation, redacted log capture,
  retention, and diagnostic envelope authority. Operations contribute lifecycle
  events and references, not a second logging system.
- `cadrumo.application._journal_repository.JournalRepositoryBase` remains the
  hardened credential-free atomic file substrate. The operation journal adds a
  typed port, transition protocol, and lease semantics over it.
- Reset and profile-bundle publication records retain their domain-specific
  lifecycle and reconciliation rules. Generic supervision references or adapts
  them; it does not copy their models into `application.operations`.
- Workflow run persistence and the renderer-neutral `application.flows` engine
  retain workflow/checkpoint and wizard-state authority. An operation may invoke
  or observe them but cannot reinterpret a workflow or wizard transition as an
  operation lifecycle transition.
- `application.storage.sync_runs.SyncRunRecord` retains completed sync-surface
  provenance. It is linked from an operation receipt and never promoted into the
  generic in-flight journal.
- Existing auth acquisition locks, browser/session lifecycle contexts, atomic
  storage writers, and domain event commits remain executor-owned safety
  primitives. The supervisor owns their enclosing resource scope and terminal
  settlement without replacing their local invariants.

The implementation plan must cite the reused symbol for every capability above
and may introduce a new primitive only when a focused code census proves that no
existing authority supplies the required semantics.

### D1 - Canonical operation envelope

Introduce a strict application-owned `OperationEnvelope`, identified by an
immutable invocation `operation_id` and a stable `OperationDefinitionId`. It
carries a validated typed request, operation revision, capability declaration,
safe context references, three state axes, typed phase, pending interaction,
deadline state, reviewable outcome or proposal reference, terminal result or
refusal reference, redacted diagnostic reference, ordered event cursor, and
journal metadata when durability is enabled. A definition may reference an
existing canonical `ActionReference`, but that relationship is optional and is
never the operation's identity. Domain-specific requests, proposals, baselines,
and results remain domain-owned payloads registered with the operation
definition.

The envelope schema is stable and closed at the generic lifecycle boundary but
extensible through versioned registered request, result, phase, interaction,
event-detail, and review-payload families. Extensions cannot add new generic
state meanings by smuggling them into free-form fields.

### D2 - Independent lifecycle, terminal, and effect axes

The global lifecycle is `CREATED`, `QUEUED`, `RUNNING`,
`WAITING_FOR_INTERACTION`, `WAITING_FOR_EXTERNAL`,
`CANCELLATION_REQUESTED`, `SETTLING`, or `TERMINAL`.

The terminal condition is absent until terminal, then exactly one of
`SUCCEEDED`, `REFUSED`, `FAILED`, `CANCELLED`, `TIMED_OUT`, or `INTERRUPTED`.
The effect is independently `NONE`, `UPDATED`, `PARTIAL`, or `UNKNOWN`.
Operation-specific phases are typed codes below the global lifecycle and are
localized only by frontend projections.

### D3 - Supervisor API and settlement ownership

The application exposes `submit`, `start`, `observe`, `stream_events`,
`respond`, `request_cancel`, `await_terminal`, and `reconcile`. Observation is
revisioned and event streaming is ordered and cursor-based, so an asynchronous
consumer can detach, reconnect, replay missed events, and resume live feedback
without restarting work. Only the supervisor may advance the generic lifecycle,
enforce the aggregate deadline, publish terminal settlement, or close the owned
resource scope. Executors emit typed phase, interaction, log, effect, and result
facts through a supervisor context; they do not mutate the envelope directly.

`OperationEvent` is a discriminated, monotonically sequenced record carrying the
operation identity, envelope revision, timestamp, event kind, stable code, and
safe typed facts. `OperationLogRecord` is a structured event variant with
severity and optional redacted diagnostic correlation. Localized log lines and
status copy are projections. Retention and persistence follow the operation's
declared durability policy; secrets are rejected at the event boundary.
Streaming MUST define bounded buffering, cursor expiry, replay, and slow-consumer
behavior without allowing backpressure to stall or corrupt the operation.

This event model does not replace `cadrumo.core.observability`. Each operation
opens or joins the existing run/log capture scope and records the resulting
redacted diagnostic reference and correlation identity. Operation events carry
safe lifecycle facts and log references; the observability subsystem remains the
authority for diagnostic log capture, retention, and envelope capture.

Cleanup is part of settlement. Browsers, sessions, locks, files, child
processes, and similar resources belong to the operation scope. The lifecycle
enters `SETTLING` after execution and reaches `TERMINAL` only after resources
are released or cleanup failure is recorded. Closing a frontend detaches its
projection; it does not assert that the operation stopped.

### D3a - Credential-free request identity and ephemeral secret submission

The supervisor has two explicit, mutually exclusive request-storage policies.
`SECURE_REFERENCE` retains the current encrypted content-addressed operand
path. `CREDENTIAL_FREE_JOURNAL` is allowed only for a registry-validated,
strict, safe request model and is atomically recorded with the lifecycle
snapshot; its canonical content digest binds idempotency. It is not a fallback
encrypted store and may never hold a secret, reversible secret derivative,
callback, frontend identity, or transport bearer. This policy supplies the
durable exact target for an operation that must obtain a secret before a DEK
exists; no executor may reconstruct a special request from its subject as an
alternative persistence path.

The application operation facade exposes one `EphemeralSecretSubmission` port,
owned by the same supervisor that owns the operation. A definition that declares
the capability supplies a durable, credential-free secret requirement containing
only the operation identity, definition, subject, interaction identity and
revision, secret kind, and expiry. The port accepts a runtime-only secret input
only when that exact requirement is live; it refuses mismatch, stale revision,
expiry, duplicate submission, or an already-consumed requirement. The broker
retains the input only in process memory, binds it to that requirement, consumes
it once for the registered executor, and zeroises it on consume, expiry,
cancellation, terminal settlement, supervisor shutdown, and owner cleanup.
Neither the input nor a digest or callback derived from it enters an envelope,
journal, event, receipt, diagnostic, response, projection, trace, or retained
frontend state.

A created secret-wait is a pre-effect state. If restart reconciliation proves
that no runtime broker secret survives and no executor entry was recorded, the
supervisor settles it `INTERRUPTED` with effect `NONE`; it does not resume,
re-prompt, derive, or retain the secret. Once executor entry is recorded, the
ordinary owner-loss rule remains `UNKNOWN` unless the executor's authoritative
domain receipt proves a narrower effect. Requirement expiry and pre-entry
cancellation clear the broker and settle with effect `NONE`; expiry is a secret
submission bound, not an aggregate execution deadline. This is a generic
supervisor capability, not a profile-login exception. Its conformance suite
must prove exact binding, single consumption, every refusal, cleanup,
non-retention, pre-entry restart interruption, and post-entry uncertainty.

### D4 - Typed interaction and exact approval binding

Operator interaction is a discriminated application contract, not a frontend
callback. A request carries immutable interaction and operation identities, an
operation revision, response schema, safe presentation facts, optional expiry,
and a digest of the exact state it continues. Responses are single-use; stale,
duplicated, mismatched, or expired responses are refused.

Approval is a specialized interaction. It binds the exact request, baseline,
reviewed proposal, proposed effect digest, actor, and time. Execution consumes
that approved operand and MUST NOT silently re-read, rebuild, or substitute a
different proposal. A changed baseline returns to typed review or settles as a
stale refusal according to domain policy.

An asynchronous executor may publish a typed `REVIEW_READY` interaction with a
reviewable proposal or provisional outcome while remaining
`WAITING_FOR_INTERACTION`. The generic response API carries explicit `APPLY` or
`REJECT` intent, plus operation revision and proposal digest. `APPLY` resumes the
registered effect phase using exactly that operand; `REJECT` records a typed
rejection result and settles with no governed effect. A proposal is never
reported as the authoritative terminal result before this continuation settles.

### D5 - Declared durability, cancellation, and deadlines

Each operation declares `EPHEMERAL`, `RECORDED`, or `RESUMABLE` durability.
Ephemeral mode is permitted only when lost observation cannot conceal an effect
requiring reconciliation. Completed domain provenance may be referenced by a
terminal operation but does not replace lifecycle persistence.

Cancellation is `UNSUPPORTED`, `COOPERATIVE`, or `CONTAINED`. Cooperative
executors receive a cancellation scope and acknowledge safe stopping; contained
executors run behind a supervisor-owned task or process boundary that can be
stopped and reaped. Cancellation request and completion remain distinct.
Deadlines are absent, cooperative, or enforced. A displayed countdown derives
from supervisor state and cannot itself settle an operation.

Durable operation transitions use one optimistic revision and one atomic
snapshot-plus-event append. `submit` accepts an idempotency key scoped to the
definition and subject; replay returns the existing invocation. Before an
executor starts, the supervisor atomically claims the declared conflict scope
through a renewable owner lease. Only the current lease owner may advance the
envelope or perform effects. Lease expiry does not authorize immediate replay:
`reconcile` first proves owner loss, classifies any uncertain effect, and either
resumes from a declared checkpoint or settles `INTERRUPTED`.

Recorded schemas are versioned and migrated before acquisition. Event delivery
is at-least-once by cursor; envelope revisions and event sequence numbers make
duplicates detectable. The journal transition, lease transition, and effect
receipt boundary MUST be specified per executor wherever they cannot share one
atomic store. The supervisor is the sole orphan-reconciliation authority.

Cancellation and deadline settlement follow these rules:

- cooperative cancellation reaches `CANCELLED` only after executor
  acknowledgement and cleanup settlement;
- contained-process cancellation reaches `CANCELLED` only after process-tree
  termination, reaping, and cleanup settlement;
- a non-cooperative thread or external owner that may still run cannot settle
  `CANCELLED` or `TIMED_OUT`; it remains `CANCELLATION_REQUESTED` or `SETTLING`
  until reconciliation proves its state;
- an aggregate execution deadline requests cancellation, while a separate
  cleanup deadline controls escalation and orphan classification;
- owner loss or cleanup uncertainty settles `INTERRUPTED` with effect `UNKNOWN`
  unless an authoritative receipt proves a narrower effect;
- application shutdown requests the declared policy, waits through its bounded
  settlement window, persists remaining ownership state, and never derives an
  operation terminal state from frontend teardown.

### D6 - Canonical operation registry

One application registry, keyed by `OperationDefinitionId`, binds request and
result schemas, executor factory, phase and interaction families, approval and
baseline policy, request-storage and ephemeral-secret-submission policy,
capabilities, effect and idempotency semantics, reconciliation policy, and
permitted frontend projections. It does not extend or duplicate the
operator-action catalogue. An optional join table maps an existing
`ActionReference` to an operation definition only where a validated recovery
action launches that operation.

TUI, CLI, and MCP dispatch registered operations through the supervisor. They
may use different presentation and waiting strategies, but none may invoke an
executor, outbound adapter, or mutating business callback directly.

### D7 - Surface projections

The TUI observes envelope revisions and renders lifecycle, phase, interaction,
progress, structured live logs, cancellation availability, deadline, reviewable
outcome, apply/reject affordances, effect, and terminal state. Spinner visibility
is derived from the envelope's executing or settling lifecycle and stops only on
an authoritative waiting or terminal state. Textual workers and stream
connections may relay observation but are never operation state.

The CLI may synchronously submit and await, then project the authoritative
terminal result through its existing success/error envelope, notice, text, and
exit-code contracts. MCP may relay progress and cancellation through transport
facilities, but transport timeout or disconnection cannot falsely settle the
application operation.

The CLI exposes one root-owned global `--tui` request before command execution. After
the complete path is resolved, `TuiCapability.AVAILABLE` means a real callable
full-screen interface exists today and is invoked; `NOT_IMPLEMENTED` returns the
localized typed `TUI_NOT_IMPLEMENTED` refusal. Explicit `--tui` never falls back to
line mode. Help, version, completion, and equivalent introspection take precedence.

Availability and migration state are separate facts. Until the dedicated
`cadrumo.entrypoints.tui` launcher replaces them, the existing bounded CLI consumers
of `cadrumo.adapters.inbound.tui` remain authorized for commands marked `AVAILABLE`.
No new legacy consumer may be added. This transitional exception does not satisfy any
dedicated-launcher, packaging, reverse-consumer, legacy-deletion, or campaign-close gate.

### D7a - Generic operation modal

`OperationModal` is the operation-agnostic Textual projection of an
`OperationEnvelope`. The host owns mounting, focus, and the observation
subscription; the supervisor owns the operation, executor task or contained
process, interactions, resources, deadline, cancellation, effects, and
settlement. The modal holds only operation ID, event cursor, latest revision,
pending interaction ID, and render-local state.

The modal derives phase, progress, structured logs, review content, spinner,
enabled controls, cancellation availability, effect, and terminal copy from
supervisor snapshots. It MUST NOT execute business work, translate Textual
worker state into operation state, retain a business result as authority, close
an operation resource, or kill a subprocess directly.

The operation definition declares one close policy:

- `DETACH_ALLOWED`: close unsubscribes and the operation remains observable and
  reopenable by operation ID.
- `REQUEST_CANCEL`: close intent issues `request_cancel` and the modal remains
  attached through cancellation acknowledgement and settlement.
- `BLOCK_UNTIL_SETTLED`: close is refused while the registered irreversible or
  non-detachable section remains active.

Window close, Escape, unmount, and navigation never manufacture approval,
rejection, cancellation completion, success, abandonment, or failure.
Apply/reject dispatch `respond` for the exact pending interaction; Cancel
dispatches `request_cancel`. A pending interaction survives detachment. Even
when execution uses a contained subprocess, the supervisor owns its handle,
heartbeat, termination, reaping, and reconciliation. TUI application shutdown
uses supervisor shutdown policy rather than modal teardown.

### D8 - Structural and behavioral conformance

Add a fixed-point operation-exposure census joining operation definitions, TUI
actions, CLI and MCP projections, executor factories, direct mutation/outbound
sites, and declared exclusions. Every operation exposure joins exactly one
operation definition and every exposure claim joins a real surface.
Opaque action callables, frontend-owned `asyncio.run`, direct outbound calls
from inbound projections, and unregistered worker-based mutations fail the
gate. Permanent allowlists and aggregate counts are insufficient.

The command-graph gate distinguishes callable availability from dedicated-migration
completion. It proves every `AVAILABLE` command joins a real full-screen interface,
every `NOT_IMPLEMENTED` request returns the typed refusal, explicit requests never
fall back to line mode, and introspection never launches a frontend. A separate
migration gate remains red while an authorized transitional CLI-to-inbound-TUI import
exists; capability tests cannot satisfy or waive that gate.

The accepted recovery-action census remains separate and authoritative for
`ActionReference`, verdict, command-leaf, result-schema, and MCP exposure joins.
Where a recovery action dispatches an operation, a third join validates exactly
one action-to-operation mapping. Neither census reimplements the other's scanner
or identity rules.

Registry-driven tests exercise each executor according to declared capability:
success, refusal, failure, exact-once settlement, effect reporting, stale or
mismatched interaction, deadline behavior, cancellation at declared safe
points, frontend detachment, cleanup failure, and restart reconciliation.
Projection tests prove TUI, CLI, and MCP render authoritative state without
becoming lifecycle owners.

### D9 - Migration and grounded acceptance call sites

The opaque manager action execution seam and independent credential worker
lifecycle are retired as operation authorities. Existing visual components may
remain as projections during a tracked, shrinking migration census, but every
new operation must enter through the supervisor immediately.

Census synchronization is the mandatory end-to-end acceptance case because it
combines external authentication, device waiting, acquisition, typed review,
exact approval, stale-baseline detection, local mutation, progress, deadline,
cancellation, browser cleanup, and durable reconciliation. It must prove no
effect before approval, consumption of the reviewed operand, one operation ID
across all phases, authoritative cleanup before settlement, declared restart
behavior, and equivalent CLI/TUI semantics. Census field intent, merge policy,
phase, and persistence rules remain domain decisions and do not enter the
generic envelope.

Register census pull, review, and apply as one `RESUMABLE` operation with an
exact-baseline approval policy. It is cooperatively cancellable outside the
atomic profile-apply section, where `cancellable_now` becomes false. Acquisition
or `REJECT` settles with effect `NONE`; successful application settles
`UPDATED`; storage ambiguity settles honestly as `UNKNOWN`. One operation ID
must span Cl@ve external-device waiting, remote read, durable review, apply, and
resource settlement. The exact reviewed operand is applied through the existing
`apply_cotejo` authority; this ADR creates no second census writer.

The accepted census policies are reconciled as follows. Explicit review remains
mandatory because censo autofill reconciles AEAT observations with an
operator's declarations; the generic sync-control ruling for mirrors and
observation caches does not displace that consent boundary. The reviewed
observation, baseline revision and digest, field intents, and proposed-effect
digest form one encrypted, content-addressed operand. Approval binds the exact
operand and baseline. Apply delegates exclusively to `apply_cotejo` inside the
supervisor's irreversible section; no operation module may reproduce its merge
or write path. A stale baseline returns to review or refuses with effect `NONE`.
Resume consumes the persisted interaction checkpoint and secure operand and
must not repeat the remote read after review. These refinements are grounded in
`2026-08-24-tui-architecture-censo-operation-authority-reconciliation-research`.

Checkpoint publication is supervisor-owned. The executor context exposes a
typed secure-operand store for results produced after submission; publishing a
review interaction atomically persists that operand and journals only its
content digest. Consuming an apply or reject response durably records the
continuation intent and schedules the registered executor from the same
checkpoint. Startup reconciliation must recover both unconsumed review waits
and consumed-but-unsettled continuations from that durable state. Initial
execution may perform remote acquisition once; every review, response, and
restart continuation resolves the stored operand and is forbidden to reacquire.
The sole profile mutation remains the `apply_cotejo` compare-and-swap inside
the supervisor's irreversible section.

Register previous-filing history pull-all as one scoped `RECORDED` operation,
not initially resumable. The nested bulk-capture service already supports
`dry_run`, but the composed `pull_filed_history` operation does not expose it;
adding dry-run to the registered operation is therefore new API work and must
preserve identical discovery scope while producing effect `NONE`. A normal run
does not gain an unrelated generic approval ceremony merely because it writes.
Each captured observation is an atomic effect unit, so the outer effect may be
`NONE`, `UPDATED`, or `PARTIAL`. The completed `SyncRunRecord` remains domain
provenance referenced by the operation result, not the lifecycle journal.

Filing-history cancellation and aggregate timeout are initially
`UNSUPPORTED`. They may become cooperative only after the executor consumes the
supervisor cancellation scope, acknowledges between atomic units, records
checkpoints and actual committed effect, and proves cleanup before settlement.
Acceptance requires ordered discovery, pair, declaration, persistence, IVA
wallet, notification, and cleanup progress under one operation ID; typed
failure scope; effect equal to committed units; no dry-run provenance; and no
false cancelled or timed-out state while work continues.

Review requirements remain domain policy. Refused versus empty pairs and all
notices are always reviewable result projections. If recapture divergence or
wallet mutation later requires approval, the history executor must stage the
exact proposal before its governed write and use the same `REVIEW_READY`
apply/reject interaction. A post-write modal cannot retroactively supply
consent.

### D10 - Build-authoritative package topology

Closed, frontend-neutral operation axes live in
`src/cadrumo/core/operations.py`: lifecycle, terminal condition, effect,
durability, cancellation, deadline, close policy, event kind, and interaction
kind. This module contains value types only and imports no outer layer.

The operation platform lives at `src/cadrumo/application/operations/` with this
fixed ownership:

```text
cadrumo/application/operations/
  __init__.py          # sole public operation-platform facade
  _models.py           # envelope, snapshot and receipt models
  _capabilities.py     # validated per-operation declarations
  _events.py           # ordered event and redacted log records
  _interactions.py     # request and response contracts
  _executor.py         # executor context and protocol
  _registry.py         # operation definitions and fixed-point catalogue
  _supervisor.py       # submit/start/observe/respond/cancel/settle/reconcile
  _secret_submission.py # runtime-only supervisor-owned one-shot secret broker port
  _journal.py          # journal and lock ports only
```

Initial operation executors remain with their application owners:
`src/cadrumo/application/user_profile/_censal_operation.py` and
`src/cadrumo/application/live/_filed_history_operation.py`. Their definitions
are exported only through the owning package facades.

The operation platform reuses `JournalRepositoryBase` as the hardened,
credential-free atomic file substrate rather than declaring a second generic
journal implementation. Existing reset and bundle-export journals remain their
domain authorities and are adapted through operation definitions only when they
need generic supervision; they are not migrated into a replacement record.
Generic lifecycle rows contain identifiers, revisions, safe state, digests, and
secure references only. Sensitive census proposals and other confidential
operands remain in their existing encrypted domain storage and are referenced by
digest. The owner-lease and transition adapter lives under
`src/cadrumo/adapters/persistence/operations/`; it composes the existing atomic
substrate and storage locks but does not redefine their security guarantees.

Entrypoints own concrete construction. `cadrumo.entrypoints.tui.launcher`
composes public application operation APIs with concrete persistence and
resource adapters for the TUI. CLI and MCP compose the same frontend-neutral
application services within their own entrypoint roots and do not import the
TUI. Composition introduces no new top-level package and contains no operation
policy.

The canonical production TUI root is `src/cadrumo/entrypoints/tui/`. All
Textual imports, widgets, screens, presentation models, frontend controllers,
frontend selection, terminal themes, TUI tests, and TUI development harnesses
live below this root.

```text
cadrumo/entrypoints/tui/
  __init__.py          # INTERFACE: narrow public facade only
  __main__.py          # INTERFACE: delegates only to launcher.main
  launcher.py          # INTERFACE: TUI composition root; consumes backend
  app.py               # JOIN: navigation and area composition only
  components/          # INTERFACE: TUI-local visual mechanics only
    __init__.py
    theme.py
    widgets.py
    forms.py
    dialogs.py
    status.py
    errors.py
    logs.py
  operations/
    __init__.py        # OPERATIONS: narrow operation-projection facade
    controller.py      # OPERATIONS: supervisor API calls only
    modal.py           # OPERATIONS: generic OperationModal
    projection.py      # OPERATIONS: envelope to immutable TUI view model
    interactions.py    # OPERATIONS: typed renderers, never domain policy
    logs.py             # OPERATIONS: cursor/subscription projection
  profile/             # INTERFACE: profile task projections
    __init__.py
    app.py
    overview.py
    editor.py
    status.py
    sync_review.py
  secret/              # INTERFACE: ephemeral secret-entry projections
    __init__.py
    credentials.py
    login.py
    registration.py
    passphrase.py
  flows/               # INTERFACE: renderer over application.flows only
    __init__.py
    app.py
    question.py
    review.py
    projection.py
    dialogs.py
  modelo/              # RESERVED: do not create until a Modelo campaign
    view/               # RESERVED future home; no importable module yet
    edit/               # RESERVED future home; no importable module yet
  devtools/             # INTERFACE: TUI-only pilot/replay/surface tooling
  tests/                # INTERFACE/OPERATIONS: follows module ownership
```

`INTERFACE` rows belong to the `tui-interface` concern, `OPERATIONS` rows to
this concern, and `JOIN` rows to an explicit integration step after both lanes
are complete. `RESERVED` rows establish ownership only: they MUST NOT be created
as empty importable packages or used until a future Modelo ADR defines real
contracts and tests.

`components` contains reusable TUI presentation mechanics only. It owns no
application lifecycle, domain policy, persistence, outbound access, wizard
state, or frontend composition. `forms.py` owns
immutable visual form contracts and widgets, not validation or orchestration;
`logs.py` owns bounded log rendering, not subscription or retention; and
`errors.py` renders already-safe canonical error envelopes without accepting raw
exceptions or reclassifying failures.

Packaging adds a dedicated console entry point targeting
`cadrumo.entrypoints.tui.launcher:main` directly. CLI modules do not import the
TUI to start it. The existing automatic CLI-to-TUI import path is retired rather
than kept as a shim.

The human CLI exposes `aeat --tui [COMMAND_PATH]` as one root-owned routing request.
While the dedicated launcher remains incomplete, an `AVAILABLE` command may invoke its
existing callable full-screen interface through the bounded legacy CLI-to-inbound-TUI
seam. A genuinely unimplemented command refuses with `TUI_NOT_IMPLEMENTED`; explicit
`--tui` never falls back to line mode. Introspection takes precedence.

This temporary authorization is not the target topology. Packaging must still add the
dedicated launcher, migrate every enrolled route and reverse consumer, remove CLI
imports of TUI implementation, and delete the legacy inbound TUI without a compatibility
facade. Current capability metadata cannot mark any of those steps complete.

That retirement cannot land ahead of a replacement for the accepted frontend
selection contract. Existing commands preserve line-mode fallback and
capability negotiation through frontend-neutral application contracts; a
full-screen TUI starts through its installed entrypoint rather than a CLI import.
The affected composition clauses in `2026-07-23-tui-wizard-substrate-adr` and
`2026-07-24-profile-bundle-tui-adr` must be amended without changing their
application-owned flow semantics.

### D11 - Strict dependency direction

`cadrumo.entrypoints.tui` is an outermost entrypoint package. No backend
package, CLI or MCP entrypoint, shared test utility, or development tool may
import, load, re-export, annotate against, or register from it. Packaging
metadata and out-of-process smoke execution are the only external references.
TUI-specific tests live in `cadrumo.entrypoints.tui.tests`; pilot, replay,
screenshot, and surface tools live in `cadrumo.entrypoints.tui.devtools`.

No Textual class, widget, screen, CSS/theme rule, TUI form or dialog, TUI view
model, terminal interaction controller, TUI frontend-selection function, or TUI
test utility may live outside `src/cadrumo/entrypoints/tui/`. Backend packages retain only
frontend-neutral application/domain contracts that CLI, MCP, TUI, and future
interfaces may consume independently. A model is not made backend-neutral by
renaming it if its fields encode screen, widget, modal, spinner, keyboard,
terminal-layout, or localized presentation concerns.

Inside the boundary:

- `cadrumo.entrypoints.tui.launcher` is the concrete TUI composition root and
  the only TUI module allowed to wire concrete adapters.
- `app.py`, `operations`, `profile`, `secret`, and `flows` consume injected
  dependencies plus public application and core facades. They MUST NOT import
  concrete adapters, repositories, private application modules, CLI or MCP, or
  domain internals.
- `cadrumo.application.operations` MUST NOT import Textual, a frontend or
  entrypoint or concrete adapter.
- Adapter implementations never import entrypoints.
- `components` may depend on Textual and layer-neutral core presentation
  primitives, but not on TUI feature packages, `app`, or `launcher`.
- `operations`, `profile`, `secret`, and `flows` may share only `components`;
  they do not import one another. `app.py` is their TUI composition point.
- Cross-package callers use `cadrumo.application.operations` and owning
  application package facades. Deep private imports are forbidden.
- `cadrumo.entrypoints.tui.__init__` exports only launcher-level public API.

Import-linter enforces both directions, the launcher-only concrete-wiring
exception, component independence, and adapter-to-entrypoint prohibition. An
AST gate also rejects dynamic strings, `TYPE_CHECKING`, re-export, annotation,
registration, and plugin-discovery bypasses; Textual imports outside the TUI
entrypoint; TUI-named presentation types outside its root; and private-facade
reaches.

### D12 - Separate migration lanes before wizard restructuring

The operation-platform lane owns `cadrumo.core.operations`,
`cadrumo.application.operations`, the persistence operation adapter,
application-owned executors, `cadrumo.entrypoints.tui.operations`, and
`OperationModal`.

The `tui-interface` lane owns `entrypoints.tui.components`, `profile`, `secret`,
`flows`, `devtools`, and presentation-owned tests. It MUST NOT edit operation
lifecycle, supervisor, journal, executor, or application flow semantics. The
operation lane MUST NOT edit navigation, visual design, wizard semantics, or
secret-entry presentation.

The integration lane owns `entrypoints.tui.__init__`, `__main__`, `launcher`,
`app`, packaging metadata, and root navigation. It lands only after the two
foundational lanes are green. `components` is the only shared TUI-local
presentation seam; the operation lane consumes its facade but places no
lifecycle or policy there.

The current reverse imports form a generated migration manifest keyed by exact
module, imported symbol, and consumer class. It includes every production
entrypoint, the full legacy facade export set, application parity test, TUI-owned
tests, manager pilot, and `dev/tui` surface - not only the currently named manager
and wizard examples. Each row records its owning lane, replacement public
facade or out-of-process boundary, and deletion proof. The manifest is generated
from AST discovery and checked against `rg`; prose counts and allowlists are not
authoritative. No new identity may enter it.

Completion requires no TUI or Textual code outside `entrypoints.tui`, no outside
Python imports of that package, an empty legacy inventory, exact joins among
operation definitions, entrypoint composition, and TUI/CLI/MCP projections,
the separate accepted recovery-action census remaining green, and deletion of
`cadrumo.adapters.inbound.tui` without a compatibility facade.

### D13 - One authorizing plan and no parallel implementation plans

Implementation is governed by one canonical `tui-architecture` roll-up plan.
Related frontend work may have its own information-architecture plan, but it
MUST NOT duplicate this plan's operation platform or package migration.

Before S39 registers profile login, the roll-up plan must add and close the
generic `EphemeralSecretSubmission` prerequisite: credential-free request
storage, the supervisor-owned one-shot broker, restart and cleanup semantics,
and real non-retention conformance. S39 then composes that public capability and
the existing profile-login authority exactly once; it must not introduce a
per-login callback, persistence exception, or shadow authentication path.

The roll-up plan schedules foundations upward: structural census and dependency
gates; core operation axes and application contracts; registry, supervisor,
journal ports, and persistence adapter; real executor lifecycle proofs; TUI
components and mechanical presentation relocation; TUI operation projections;
census and filing-history integration; launcher/app/packaging composition;
reverse-consumer migration and legacy deletion; then real-behavior lifecycle,
installed-entrypoint, and terminal-size verification. Every step names its
owned modules and deletion proof. A step cannot close while a legacy import,
Textual module, TUI test helper, or development surface remains outside
`entrypoints.tui`.

## Rationale

The chosen design is the only option that places execution truth with the layer
that observes validated intent, policy, interaction, resources, effects, and
cleanup. Presentation DTOs and shared events cannot make cancellation or
settlement authoritative, while reusing the CLI wire envelope would invert the
established projection boundary (`2026-08-11-tui-architecture-research`).

Three independent axes prevent a terminal label from hiding committed or
uncertain effects. Capability declarations prevent the interface from promising
cancellation, deadlines, or resumability that an executor cannot provide.
Exact interaction binding closes the gap between what an operator reviewed and
what the application performs. The distinct operation registry joins existing
recovery actions only where dispatch actually connects them, preserving the
accepted action catalogue's narrower authority
(`2026-08-09-cli-action-envelope-hardening-adr`).

## Consequences

- Every current and future frontend-triggered operation gains one authoritative
  identity, lifecycle, interaction protocol, deadline source, cleanup boundary,
  and terminal receipt.
- TUI progress, spinner, controls, cancellation, and restart/resume become
  projections of application state rather than Textual worker mechanics.
- Long-running asynchronous work exposes replayable live feedback and redacted
  logs under one operation identity, including detach and reconnect.
- Reviewable results enter one typed apply/reject continuation, allowing future
  operations to separate computation from effect without inventing a modal or
  callback contract.
- CLI and MCP retain established wire contracts while sharing execution
  semantics with the TUI.
- Approval becomes auditable and exact; a frontend gesture cannot authorize
  changed input or a changed baseline.
- Cancellation claims become honest, and operations that cannot stop safely
  expose that limitation instead of a false control.
- The fixed-point gates make bypasses mechanically detectable and bind future
  tool implementations to the architecture.
- Migration is broad: manager actions, credential attempts, progress callbacks,
  and direct frontend orchestration must move behind registered executors.
- Durable supervision adds credential-free lifecycle journal volume, leases,
  reconciliation, revision, and retention obligations. Sensitive operands remain
  in encrypted domain storage and are referenced by digest.
- The effect axis exposes partial and uncertain outcomes but requires executors
  to report post-commit failures honestly.
- Census becomes a demanding proof of the platform contract without turning
  the general architecture into census-specific machinery.
