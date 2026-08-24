---
tags:
  - '#plan'
  - '#tui-architecture'
date: '2026-08-11'
tier: L3
related:
  - '[[2026-08-11-tui-architecture-adr]]'
  - '[[2026-08-11-tui-architecture-research]]'
modified: '2026-08-24'
body_hash: 'sha256:203771b93684f89489e37f2b0764bd8876b3f994f1675e1e87eb5f372913c4b8'
---

# `tui-architecture` plan

Build the frontend-neutral operation platform first, then layer the canonical Textual entrypoint, operation reviews, cutover, and real-behavior proof.

## Description

This L3 plan executes the accepted `tui-architecture` ADR. It preserves the existing hexagonal roots: reusable execution semantics live in core, application, and adapter packages, while every Textual implementation lives under `cadrumo.entrypoints.tui`. Waves are dependency ordered so presentation never becomes the test harness for an unfinished backend contract.

### Approval and execution dependencies

The plan was explicitly approved on 2026-08-11. Its execution is nevertheless `BLOCKED` until the in-flight canonical `casilla-schema` campaign in `2026-08-10-casilla-schema-plan.md` has landed completely and its closing structural checks are green. Research, review, and dependency reconciliation may continue while blocked, but no implementation Step in this plan may start.

`tui-interface` is a downstream campaign. It MUST NOT begin implementation until this `tui-architecture` plan has landed completely and its final acceptance gates are green. That campaign may continue research and reconcile its proposed structure while blocked, but it must consume the operation platform, package boundary, and canonical `entrypoints/tui` seams delivered here rather than redeclare or build them independently.

## Steps

## Wave `W01` - Architecture gates and operation contracts

Freeze the dependency boundary, migration inventory, and frontend-neutral operation types before any executor or Textual work begins.

### Phase `W01.P01` - Structural inventory and dependency gates

Create an exact migration census and enforce the final hexagonal and TUI dependency directions before code is moved.

- [x] `W01.P01.S01` - Generate the exact legacy TUI migration manifest with module, symbol, consumer, owner lane, replacement, and deletion proof; `dev/quality/import_hygiene_scan.py`.
- [x] `W01.P01.S02` - Enforce the hexagonal TUI boundary, launcher-only adapter wiring, and backend prohibition contracts; `.importlinter`.
- [x] `W01.P01.S03` - Reject static, dynamic, type-only, re-export, registration, Textual-location, and private-facade bypasses; `src/cadrumo/tests/test_import_hygiene_gate.py`.
- [x] `W01.P01.S04` - Reconcile accepted wizard and profile-bundle composition clauses with the dedicated TUI entrypoint; `.vault/adr`.
- [x] `W01.P01.S05` - Prove the generated migration manifest matches direct source discovery and admits no new identity; `src/cadrumo/tests/test_tui_migration_manifest.py`.

### Phase `W01.P02` - Operation type foundation

Define the closed lifecycle axes, capability declarations, envelopes, events, interactions, and public application facade.

- [x] `W01.P02.S06` - Implement the closed operation lifecycle, terminal, effect, durability, cancellation, deadline, close-policy, event, and interaction axes; `src/cadrumo/core/operations.py`.
- [x] `W01.P02.S07` - Define immutable operation request, identity, snapshot, revision, and terminal receipt models; `src/cadrumo/application/operations/_models.py`.
- [x] `W01.P02.S08` - Define validated per-operation capability declarations and forbidden capability combinations; `src/cadrumo/application/operations/_capabilities.py`.
- [x] `W01.P02.S09` - Define ordered phase, progress, safe-log, effect, notice, diagnostic, and terminal event contracts; `src/cadrumo/application/operations/_events.py`.
- [x] `W01.P02.S10` - Define revision-bound interaction requests, single-use response tokens, proposal digests, and apply or reject responses; `src/cadrumo/application/operations/_interactions.py`.
- [x] `W01.P02.S11` - Expose the sole public operation-platform API without leaking private models or frontend types; `src/cadrumo/application/operations/__init__.py`.
- [x] `W01.P02.S12` - Prove state-axis independence, capability validation, exact response binding, and event redaction invariants; `src/cadrumo/application/operations/tests`.

## Wave `W02` - Durable operation supervision

Build the registry, journal, leases, event stream, cancellation, deadline, cleanup, and recovery substrate that owns operation truth.

### Phase `W02.P03` - Executor registry and context

Define registered executors, canonical action joins, resource ownership, and invocation context without frontend dependencies.

- [x] `W02.P03.S13` - Define executor context, cancellation scope, deadline access, event emission, secure operand lookup, and cleanup ownership; `src/cadrumo/application/operations/_executor.py`.
- [x] `W02.P03.S14` - Define the immutable operation registry, closed reconciliation and frontend projection declarations, executor-factory binding, and registry-owned concrete typed request and snapshot resolver keyed by definition identity with fail-closed unknown and mismatch refusal; `src/cadrumo/application/operations/_registry.py, src/cadrumo/application/operations/__init__.py, and direct registry/facade tests`.

### Phase `W02.P04` - Journal, leases, and persistence

Persist safe lifecycle state and ordered events atomically while keeping confidential operands in encrypted domain storage.

- [x] `W02.P04.S17` - Define lifecycle journal, ordered event stream, deterministic owner-lease observations distinguishing absent, active, and expired state, explicit caller-supplied observed-at lease acquire, inspect, exact-predecessor compare-and-swap, and release signatures, secure reference ports, and a strict versioned credential-free persisted snapshot contract carrying a ContentDigest secure request reference plus safe state and events while runtime snapshots remain concretely typed; `src/cadrumo/application/operations/_journal.py, src/cadrumo/application/operations/_leases.py, src/cadrumo/application/operations/_replay.py, src/cadrumo/application/operations/__init__.py, and direct journal, lease, replay, and facade tests`.
- [x] `W02.P04.S18` - Implement the operation lifecycle journal over the existing atomic journal substrate with two-hop public JournalRepositoryBase promotion, canonical operation-journal storage taxonomy, location and path grammar, durable-compatibility enrollment, concrete typed snapshot hydration, and atomic filesystem compare-and-swap tests; `src/cadrumo/application facade, src/cadrumo/adapters/persistence/operations/_journal.py, operation storage taxonomy/location/grammar and durability gates, and focused real-filesystem tests`.
- [x] `W02.P04.S19` - Implement durable owner lease acquisition, renewal, conflict refusal, expiry observation, exact-predecessor release, and expired-owner takeover evidence, and require operation journal commits to verify the exact current live lease while holding the same JournalRepositoryBase lock; `src/cadrumo/adapters/persistence/operations/_lease.py, src/cadrumo/adapters/persistence/operations/_journal.py, and focused real-filesystem lease and journal tests`.
- [x] `W02.P04.S20` - Expose the persistence adapter facade without exporting implementation internals; `src/cadrumo/adapters/persistence/operations/__init__.py`.
- [x] `W02.P04.S21` - Prove atomic snapshot and event commits, monotonic cursors, idempotent replay, lease conflicts, takeover, and credential-free persistence; `src/cadrumo/adapters/persistence/operations/tests`.

### Phase `W02.P05` - Supervisor lifecycle and recovery

Implement authoritative submission, observation, response, cancellation, deadlines, settlement, and startup reconciliation.

- [x] `W02.P05.S22` - Implement submit, start, inspect, observe, await, respond, reject, request-cancel, detach, settle, and reconcile operations with a durable idempotent claim under the journal lock, schema-v2 migration before lease acquisition, persisted pending and consumed interaction checkpoints with safe events, exact single-use response binding across restart, conflict-scope lease addressing, definition-bound executor context that refuses undeclared phase, effect, and typed cleanup-family registration before mutation, encrypted content-addressed secure references, and full journal and lease compare-and-swap invariants; `src/cadrumo/application/operations/_models.py, src/cadrumo/application/operations/_events.py, src/cadrumo/application/operations/_interactions.py, src/cadrumo/application/operations/_leases.py, src/cadrumo/application/operations/_journal.py, src/cadrumo/application/operations/_executor.py, src/cadrumo/application/operations/_supervisor.py, src/cadrumo/application/operations/__init__.py, src/cadrumo/adapters/persistence/operations/_lease.py, src/cadrumo/adapters/persistence/operations/_journal.py, src/cadrumo/adapters/persistence/operations/_secure_refs.py, src/cadrumo/adapters/persistence/operations/__init__.py, and focused application and real-filesystem persistence tests`.
- [x] `W02.P05.S16` - Prove through the production supervisor executor context that duplicate registry identities and definition-undeclared effects, phases, and resource-family ownership are refused before event or journal mutation; `src/cadrumo/application/operations/tests/test_executor_contract.py`.
- [x] `W02.P05.S23` - Implement cursor replay and bounded live observation without making subscriber connectivity operation authority; `src/cadrumo/application/operations/_supervisor.py`.
- [x] `W02.P05.S24` - Implement aggregate deadline, cooperative cancellation acknowledgement, irreversible-section protection, and cleanup deadlines; `src/cadrumo/application/operations/_supervisor.py`.
- [x] `W02.P05.S25` - Normalize expected refusals and unexpected failures into safe terminal diagnostics while retaining correlation evidence; `src/cadrumo/application/operations/_supervisor.py`.
- [x] `W02.P05.S26` - Reconcile non-terminal journal entries into resumed, recovered, interrupted, or orphaned states at startup; `src/cadrumo/application/operations/_supervisor.py`.
- [x] `W02.P05.S27` - Prove every terminal condition waits for resource cleanup and preserves the truthful effect axis; `src/cadrumo/application/operations/tests/test_supervisor_lifecycle.py`.
- [x] `W02.P05.S28` - Prove detach, cursor replay, duplicate response refusal, cancellation races, deadline races, and restart reconciliation with real journal storage; `src/cadrumo/application/operations/tests/test_supervisor_recovery.py`.

### Phase `W02.P18` - Explicit TUI invocation contract

Expose one global TUI request now, refuse every unenrolled command path explicitly, and preserve the dedicated sibling-entrypoint boundary.

- [x] `W02.P18.S105` - Declare and capture the global --tui root option; `src/cadrumo/entrypoints/cli/_root_command_specs.py, src/cadrumo/entrypoints/cli/_root_cli.py`.
- [x] `W02.P18.S106` - Refuse unenrolled TUI routes through a typed localized command-boundary error; `src/cadrumo/entrypoints/cli/_command_runtime.py, src/cadrumo/entrypoints/cli/_errors.py, src/cadrumo/core/errors/registry/_entrypoints.py`.
- [x] `W02.P18.S107` - Remove the duplicate profile-local TUI option and align password boundary tests; `src/cadrumo/entrypoints/cli/_config, src/cadrumo/core, src/cadrumo/application/user_profile, src/cadrumo/adapters/inbound/tui`.
- [x] `W02.P18.S108` - Prove global TUI refusal and locale parity across representative command facets; `src/cadrumo/entrypoints/cli/tests, src/cadrumo/locales`.
- [x] `W02.P18.S109` - Audit every production full-screen launch site and distinguish current callable availability from dedicated-entrypoint migration completion; `.vault/reference/2026-08-24-tui-architecture-command-enrollment-parity-reference.md`.
- [x] `W02.P18.S110` - Enroll the complete existing eight-route TUI surface and remove the accidental leaf-local option; `src/cadrumo/entrypoints/cli/_config, src/cadrumo/entrypoints/cli/_modelo_work_command_specs.py, src/cadrumo/entrypoints/cli/_modelo_nonwork_command_specs.py`.
- [x] `W02.P18.S111` - Prove the graph-wide available-route fixed point, global-only option placement, implemented-route dispatch, and representative unimplemented refusals; `src/cadrumo/entrypoints/cli/tests/test_global_tui_request.py, src/cadrumo/entrypoints/cli/_config/tests`.
- [x] `W02.P18.S112` - Reconcile the accepted availability decision with the still-open dedicated-entrypoint migration and complete a fresh honesty review; `.vault/adr/2026-08-11-tui-architecture-adr.md, .vault/adr/2026-08-11-tui-interface-adr.md, .vault/audit`.

## Wave `W03` - Application operation executors

Adapt current effectful workflows to the supervisor contract, beginning with census and filed-history proofs and then covering all shipped manager operations.

### Phase `W03.P06` - Census review operation

Model Modelo 036 acquisition, Clave device waiting, exact review, apply or reject, and cleanup as one resumable operation.

- [x] `W03.P06.S113` - Implement supervisor-owned post-submission secure checkpoint publication, durable response continuation scheduling, and restart recovery without reacquisition; `src/cadrumo/application/operations/_executor.py, src/cadrumo/application/operations/_interactions.py, src/cadrumo/application/operations/_supervisor.py, src/cadrumo/application/operations/tests`.
- [x] `W03.P06.S30` - Persist the encrypted reviewed observation, baseline revision and digest, field intents, and proposed-effect digest behind a secure reference; `src/cadrumo/application/user_profile/_censal_operation.py`.
- [x] `W03.P06.S31` - Apply only the approved proposal through the existing cotejo authority and refuse a stale baseline without effect; `src/cadrumo/application/user_profile/_cotejo_apply.py`.
- [x] `W03.P06.S29` - Implement the resumable census executor across preflight, Clave device wait, remote read, proposal construction, interaction wait, exact apply, and settlement; `src/cadrumo/application/user_profile/_censal_operation.py`.
- [x] `W03.P06.S32` - Export the census operation definition through the user-profile public facade; `src/cadrumo/application/user_profile/__init__.py`.
- [x] `W03.P06.S33` - Prove no write before apply, per-field and apply-all exactness, reject, stale refusal, detach and resume, cancellation boundaries, and cleanup; `src/cadrumo/application/user_profile/tests/test_censal_operation.py`.

### Phase `W03.P07` - Filed-history operation

Model previous-filing history pull as one recorded, partial-effect operation with stage and unit progress.

- [x] `W03.P07.S34` - Implement the recorded filed-history executor across discovery, register access, pair walk, capture, persistence, finalization, provenance, wallet, notifications, and settlement; `src/cadrumo/application/live/_filed_history_operation.py`.
- [x] `W03.P07.S35` - Expose dry-run on the composed filed-history operation with identical discovery scope and effect none; `src/cadrumo/application/live/_filed_history_operation.py`.
- [x] `W03.P07.S36` - Emit ordered safe stage and unit progress with scoped refusals and truthful none, updated, partial, or unknown effects; `src/cadrumo/application/live/_filed_history_operation.py`.
- [x] `W03.P07.S37` - Export the filed-history operation definition through the live application facade; `src/cadrumo/application/live/__init__.py`.
- [x] `W03.P07.S38` - Prove dry-run parity, committed-unit accounting, child provenance references, unsupported cancellation and deadline claims, and cleanup before settlement; `src/cadrumo/application/live/tests/test_filed_history_operation.py`.

### Phase `W03.P08` - Remaining shipped operations

Move every current manager and credential action behind registered application executors and the shared conformance contract.

- [x] `W03.P08.S114` - Implement credential-free non-secret operation requests and one-shot supervisor-owned ephemeral secret submission with exact binding, expiry, zeroisation, restart interruption, and no durable secret derivatives before registering login or passphrase operations; `src/cadrumo/application/operations, src/cadrumo/adapters/persistence/operations, and focused real persistence and lifecycle tests`.
- [x] `W03.P08.S39` - Register login, provider configuration, credential acquisition, passphrase rotation, and auth teardown as application-owned operations; `src/cadrumo/application/auth/_operation_definitions.py`.
- [ ] `W03.P08.S40` - Register profile field mutation, repeatable-row mutation, bundle export, and profile logout operations through existing user-profile authorities; `src/cadrumo/application/user_profile/_operation_definitions.py`.
- [ ] `W03.P08.S41` - Move Google export planning and application orchestration out of the CLI frontend and register its external-effect operation; `src/cadrumo/application/export/_google_operation.py`.
- [ ] `W03.P08.S42` - Expose authentication operation definitions through the authentication application facade; `src/cadrumo/application/auth/__init__.py`.
- [ ] `W03.P08.S43` - Expose profile mutation and lifecycle operation definitions through the user-profile application facade; `src/cadrumo/application/user_profile/__init__.py`.
- [ ] `W03.P08.S44` - Expose Google export operation definitions through the export application facade; `src/cadrumo/application/export/__init__.py`.
- [ ] `W03.P08.S45` - Run every production-registered executor through the shared success, refusal, failure, interaction, cancellation-capability, deadline-capability, effect, and cleanup matrix and prove the exported definition population is complete; `src/cadrumo/application/operations/tests/test_registered_executor_conformance.py`.

## Wave `W04` - Canonical TUI entrypoint and components

Rehome presentation mechanics mechanically beneath cadrumo.entrypoints.tui without changing backend policy or operation semantics.

### Phase `W04.P09` - TUI root and reusable components

Create the canonical TUI entrypoint packages and relocate presentation-only themes, widgets, forms, dialogs, status, errors, and logs.

- [ ] `W04.P09.S46` - Create the narrow TUI package facade and reserve launcher-level exports only; `src/cadrumo/entrypoints/tui/__init__.py`.
- [ ] `W04.P09.S47` - Relocate terminal theme and styling primitives without carrying application state; `src/cadrumo/entrypoints/tui/components/theme.py`.
- [ ] `W04.P09.S48` - Relocate reusable terminal widgets behind the components facade; `src/cadrumo/entrypoints/tui/components/widgets.py`.
- [ ] `W04.P09.S49` - Relocate immutable form presentation contracts and widgets without orchestration or backend validation; `src/cadrumo/entrypoints/tui/components/forms.py`.
- [ ] `W04.P09.S50` - Relocate generic dialogs while keeping approval and operation lifecycle out of component state; `src/cadrumo/entrypoints/tui/components/dialogs.py`.
- [ ] `W04.P09.S51` - Relocate status and busy presentation so it renders supplied operation state rather than owning timers or work; `src/cadrumo/entrypoints/tui/components/status.py`.
- [ ] `W04.P09.S52` - Implement safe error and bounded log renderers without accepting raw exceptions or retaining lifecycle authority; `src/cadrumo/entrypoints/tui/components`.
- [ ] `W04.P09.S53` - Prove components contain presentation mechanics only and import no feature, application-private, adapter, CLI, or repository modules; `src/cadrumo/entrypoints/tui/components/tests`.

### Phase `W04.P10` - Feature presentation relocation

Mechanically relocate profile, secret, flow, test, and development surfaces without changing application policy or wizard semantics.

- [ ] `W04.P10.S54` - Relocate profile overview, editor, status, and task projections without changing profile policy; `src/cadrumo/entrypoints/tui/profile`.
- [ ] `W04.P10.S55` - Relocate credential, login, registration, and passphrase projections while keeping secrets ephemeral; `src/cadrumo/entrypoints/tui/secret`.
- [ ] `W04.P10.S56` - Relocate the existing flow renderer mechanically without changing application flow or wizard semantics; `src/cadrumo/entrypoints/tui/flows`.
- [ ] `W04.P10.S57` - Relocate TUI-owned pilot, replay, screenshot, and terminal-surface tooling; `src/cadrumo/entrypoints/tui/devtools`.
- [ ] `W04.P10.S104` - Relocate the casilla review screen and its tests to the canonical Modelo view as a read-only consumer of the public application.modelo ModeloWorkReview facade, preserving the named-outlier evidence and deleting the legacy inbound screen, its facade exports and its locale references in the same change without a compatibility facade; `src/cadrumo/entrypoints/tui/modelo/view and src/cadrumo/adapters/inbound/tui/_modelo_work_review_screen.py`.
- [ ] `W04.P10.S58` - Move presentation tests under the canonical owning packages and remove backend imports of TUI test helpers; `src/cadrumo/entrypoints/tui/tests`.
- [ ] `W04.P10.S59` - Prove the relocation is behavior-preserving before any root app or navigation join is introduced; `src/cadrumo/entrypoints/tui/tests/test_relocation_parity.py`.

## Wave `W05` - TUI operation projection and review

Build the operation-agnostic modal, live log projection, interactions, and domain review views solely as consumers of supervisor state.

### Phase `W05.P11` - Generic operation projection

Project supervisor snapshots and ordered events into a detachable modal, live logs, progress, controls, and typed interactions.

- [ ] `W05.P11.S60` - Implement a TUI controller limited to supervisor submit, inspect, observe, respond, reject, cancel, and detach calls; `src/cadrumo/entrypoints/tui/operations/controller.py`.
- [ ] `W05.P11.S61` - Project operation snapshots and capabilities into immutable modal view models without reclassifying backend truth; `src/cadrumo/entrypoints/tui/operations/projection.py`.
- [ ] `W05.P11.S62` - Project cursor-based structured events into bounded live and historical log views with diagnostic references; `src/cadrumo/entrypoints/tui/operations/logs.py`.
- [ ] `W05.P11.S63` - Render typed input, choice, review, apply, and reject interactions through registered presentation schemas; `src/cadrumo/entrypoints/tui/operations/interactions.py`.
- [ ] `W05.P11.S64` - Implement the generic detachable operation modal with phase, progress, spinner, logs, diagnostics, interaction, cancellation, and terminal receipt regions; `src/cadrumo/entrypoints/tui/operations/modal.py`.
- [ ] `W05.P11.S65` - Expose the narrow operation-presentation facade without exporting Textual internals as backend contracts; `src/cadrumo/entrypoints/tui/operations/__init__.py`.
- [ ] `W05.P11.S66` - Derive spinner visibility, enabled controls, close policy, and terminal copy solely from supervisor projections; `src/cadrumo/entrypoints/tui/operations/projection.py`.
- [ ] `W05.P11.S67` - Prove cursor replay, detach and reattach, interaction revisions, cancellation acknowledgement, terminal settlement, log visibility, and subscriber loss; `src/cadrumo/entrypoints/tui/operations/tests`.

### Phase `W05.P12` - Domain review projections

Render census field review and filed-history outcome detail without placing domain merge or effect policy in the TUI.

- [ ] `W05.P12.S68` - Implement census local-versus-persisted field review with suggested intent, per-field selection, apply all, reject, and stale-proposal display; `src/cadrumo/entrypoints/tui/profile/sync_review.py`.
- [ ] `W05.P12.S69` - Implement filed-history stage, unit, refusal, partial-effect, evidence, wallet, notification, and provenance result projection; `src/cadrumo/entrypoints/tui/profile/sync_review.py`.
- [ ] `W05.P12.S70` - Prove census review dispatches exact typed responses and never writes or recomputes policy in the TUI; `src/cadrumo/entrypoints/tui/profile/tests/test_census_sync_review.py`.
- [ ] `W05.P12.S71` - Prove filed-history progress, scoped errors, viewable logs, child provenance, and partial outcomes remain visible through settlement; `src/cadrumo/entrypoints/tui/profile/tests/test_filed_history_operation_view.py`.

## Wave `W06` - Composition cutover and legacy deletion

Join the independently green backend and frontend lanes, migrate every reverse consumer, switch packaging, and remove the legacy adapter package.

### Phase `W06.P13` - Root composition and packaging

Compose the independently green lanes in the TUI launcher and app, then expose the dedicated installed entrypoint.

- [ ] `W06.P13.S72` - Compose every exported operation definition into one immutable production registry with concrete operation adapters, journals, resources, and the supervisor in the sole TUI composition root; `src/cadrumo/entrypoints/tui/launcher.py`.
- [ ] `W06.P13.S73` - Join profile, secret, flow, and operation areas through navigation only after both implementation lanes are green; `src/cadrumo/entrypoints/tui/app.py`.
- [ ] `W06.P13.S74` - Delegate module execution directly to the TUI launcher without importing the CLI; `src/cadrumo/entrypoints/tui/__main__.py`.
- [ ] `W06.P13.S75` - Add the dedicated installed TUI console entry point targeting the launcher directly; `pyproject.toml`.

### Phase `W06.P14` - Reverse-consumer migration

Replace every CLI, application-test, and development import of the legacy TUI with backend facades or out-of-process invocation.

- [ ] `W06.P14.S76` - Remove frontend-owned manager callbacks and consume registered operation APIs and application results only; `src/cadrumo/entrypoints/cli/_config/_manager_actions.py`.
- [ ] `W06.P14.S77` - Remove manager TUI construction and retain only CLI projection or frontend-neutral selection behavior; `src/cadrumo/entrypoints/cli/_config/_manager_frontend.py`.
- [ ] `W06.P14.S78` - Remove login TUI construction and consume the application authentication operation contract; `src/cadrumo/entrypoints/cli/_config/_login_frontend.py`.
- [ ] `W06.P14.S79` - Remove status-screen imports and project backend status through the CLI surface only; `src/cadrumo/entrypoints/cli/_config/_status_frontend.py`.
- [ ] `W06.P14.S80` - Replace profile-bundle TUI imports with application flow and operation facades; `src/cadrumo/entrypoints/cli/_config/_profile_bundle_flow.py`.
- [ ] `W06.P14.S81` - Replace descendant wizard TUI imports with frontend-neutral application flow contracts; `src/cadrumo/entrypoints/cli/_config/_descendiente.py`.
- [ ] `W06.P14.S82` - Replace representative wizard TUI imports with frontend-neutral application flow contracts; `src/cadrumo/entrypoints/cli/_config/_apoderado.py`.
- [ ] `W06.P14.S83` - Remove work-wizard imports of TUI internals while preserving line-mode and installed-TUI selection semantics; `src/cadrumo/entrypoints/cli/_modelo_work_wizard_cli.py`.
- [ ] `W06.P14.S84` - Remove amendment-wizard imports of TUI internals while preserving line-mode and installed-TUI selection semantics; `src/cadrumo/entrypoints/cli/_modelo_amend_wizard_cli.py`.
- [ ] `W06.P14.S85` - Replace application flow parity dependencies on TUI modules with backend contract assertions; `src/cadrumo/application/flows/tests/test_frontend_parity.py`.
- [ ] `W06.P14.S86` - Move the manager pilot behind the TUI devtools facade or installed out-of-process boundary; `src/cadrumo/tests/manager_pilot.py`.
- [ ] `W06.P14.S87` - Move remaining development TUI launchers and surface checks beneath the canonical TUI devtools package; `dev/tui`.

### Phase `W06.P15` - Legacy adapter removal

Close the migration manifest and delete cadrumo.adapters.inbound.tui without a compatibility facade.

- [ ] `W06.P15.S88` - Close every generated migration-manifest row with its replacement import or out-of-process proof; `dev/import_hygiene_scan.py`.
- [ ] `W06.P15.S89` - Delete the legacy inbound TUI implementation and tests without a compatibility facade; `src/cadrumo/adapters/inbound/tui`.
- [ ] `W06.P15.S90` - Remove legacy TUI exports and package registrations from the inbound adapter namespace; `src/cadrumo/adapters/inbound/__init__.py`.
- [ ] `W06.P15.S91` - Prove zero production or shared-test imports of the TUI, zero Textual outside its root, and a fully importable canonical package; `src/cadrumo/tests/test_import_hygiene_gate.py`.

## Wave `W07` - Real-behavior closure

Prove lifecycle, process cleanup, review exactness, installed-entrypoint behavior, responsive terminal rendering, and structural zero-bypass acceptance.

### Phase `W07.P16` - Lifecycle and process proof

Exercise real asynchronous resources, Clave device authentication, cancellation, deadlines, restart, recovery, and process reaping.

- [ ] `W07.P16.S92` - Exercise the production supervisor and executors against deterministic local HTTP and browser fixtures with real async resources and trace logging; `src/cadrumo/application/operations/tests/test_real_resource_lifecycle.py`.
- [ ] `W07.P16.S93` - Exercise the authenticated Clave device flow through the installed TUI operation path without QR assumptions and retain only redacted diagnostics; `src/cadrumo/entrypoints/tui/tests/integration/test_clave_device_operation.py`.
- [ ] `W07.P16.S94` - Request cancellation at every declared cancellable phase and prove acknowledgement, cleanup completion, lock release, and child-process reaping; `src/cadrumo/application/operations/tests/test_cancellation_cleanup.py`.
- [ ] `W07.P16.S95` - Enforce aggregate and cleanup deadlines without publishing timed out while execution or owned resources continue; `src/cadrumo/application/operations/tests/test_deadline_settlement.py`.
- [ ] `W07.P16.S96` - Crash and restart recorded and resumable operations to prove lease takeover, cursor replay, resume policy, and orphan reporting; `src/cadrumo/application/operations/tests/test_restart_reconciliation.py`.
- [ ] `W07.P16.S97` - Prove census and filed-history effects, provenance, interactions, and cleanup through their production application and persistence seams; `src/cadrumo/entrypoints/tui/tests/integration/test_sync_operations.py`.

### Phase `W07.P17` - TUI behavior and structural acceptance

Prove live feedback, visible diagnostics, review actions, responsive layouts, installed execution, and zero architectural bypasses.

- [ ] `W07.P17.S98` - Prove spinner, phase, deadline, cancellation availability, live logs, diagnostic detail, review content, and terminal receipts follow supervisor revisions; `src/cadrumo/entrypoints/tui/operations/tests/test_operation_modal.py`.
- [ ] `W07.P17.S99` - Prove modal detach, close refusal, apply, reject, and cancel behavior never assumes process ownership; `src/cadrumo/entrypoints/tui/operations/tests/test_operation_modal_lifecycle.py`.
- [ ] `W07.P17.S100` - Verify profile, secret, flow, and operation surfaces at narrow, normal, and wide terminal sizes; `src/cadrumo/entrypoints/tui/tests/test_terminal_sizes.py`.
- [ ] `W07.P17.S101` - Run the packaged TUI through its installed console and module entrypoints without importing CLI internals; `src/cadrumo/entrypoints/tui/tests/test_installed_entrypoint.py`.
- [ ] `W07.P17.S15` - Complete the derived live-tree fixed-point census joining every registered operation definition, recovery action, TUI, CLI and MCP exposure, executor factory, direct mutation or outbound site, and declared exclusion; `src/cadrumo/application/operations/tests/test_operation_catalogue.py`.
- [ ] `W07.P17.S102` - Re-run operation catalogue, recovery-action, migration-manifest, import-linter, AST, and Textual-location fixed-point gates; `src/cadrumo/tests`.
- [ ] `W07.P17.S103` - Run the feature validation suite and formal architecture review against the accepted ADR and exact migration inventory; `.vault/plan/2026-08-11-tui-architecture-plan.md`.

## Parallelization

The whole plan is blocked until `casilla-schema` lands. After that gate opens, Waves are sequential unless a Wave explicitly identifies independent Phases. No TUI operation projection begins before the operation models, persistence, supervisor, and executor conformance base is green. Work internal to this plan may parallelize only where a Wave says so; composition, cutover, and deletion remain serialized. The separate `tui-interface` campaign does not execute in parallel and remains blocked until this plan lands and its acceptance gates are green.

## Verification

The plan is complete when every Step is closed, the operation conformance matrix proves honest success, refusal, failure, cancellation, timeout, interruption, effect, and cleanup settlement, and the installed TUI proves live progress and review behavior at supported terminal sizes. Structural closure additionally requires no Textual or TUI implementation outside `cadrumo.entrypoints.tui`, no outside Python import of that package, no direct TUI mutation callback, and deletion of `cadrumo.adapters.inbound.tui` without a compatibility facade.
