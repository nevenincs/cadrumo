---
tags:
  - '#plan'
  - '#tui-architecture'
date: '2026-08-11'
tier: L3
related:
  - '[[2026-08-11-tui-architecture-adr]]'
  - '[[2026-08-11-tui-architecture-research]]'
  - '[[2026-08-24-tui-registry-api-gate-adr]]'
  - '[[2026-08-24-modelo-edit-contract-adr]]'
  - '[[2026-08-24-tui-modelo-workspace-interface-adr]]'
  - '[[2026-08-24-tui-registry-api-gate-architecture-reconciliation-audit]]'
modified: '2026-08-25'
body_hash: 'sha256:c5556df304f4050d7273aeb535102bffef5421d6d9893fc55915b0a111e4ca23'
---

# `tui-architecture` plan

Build the frontend-neutral operation and Modelo application contracts first, then layer the canonical Textual entrypoint, receipt-gated cohorts, current-only cutover, and real-behavior proof.

## Description

This L3 plan executes the accepted and amended `tui-architecture` ADR together with the accepted registry API gate, Modelo Edit Contract, and Modelo Workspace Interface decisions. It preserves the existing hexagonal roots: reusable execution semantics live in core, application, and adapter packages, while every Textual implementation lives under `cadrumo.entrypoints.tui`. The architecture lane owns the public operation C0 contract and receipt, Workspace V1 and its C2 dependency receipt, Edit Contract V1, the distinct transient-financial-operand protocol, and the Edit C3 dependency receipt. The interface lane owns TUI destinations and the C1 through C5 exit receipts. Waves are dependency ordered so presentation never becomes the test harness for an unfinished backend contract.

### Approval and execution dependencies

The plan was explicitly approved on 2026-08-11. Its original `casilla-schema` execution blocker is discharged: the canonical `2026-08-10-casilla-schema-plan.md` is complete at 52 of 52 Steps. This records the changed prerequisite without rewriting the earlier execution history.

Architecture and interface execution now interleave only through exact current-HEAD receipts. `W02.P19.S124` closes C0 and alone opens the existing operation-presentation Steps `S60` through `S67`. `S104` supplies the canonical review relocation evidence consumed by the interface C1 exit. Workspace V1 may be built in `W03.P20`, but `W04.P22` may mint the C2 dependency receipt only after the exact green C1 exit, and interface C2 consumes that receipt. Edit Contract V1 may be built in `W03.P21`, but C3 remains unavailable until `W05.P23` closes both the financial-operand receipt and the Edit Contract dependency receipt after C2. Lifecycle enrollment in `W06.P24` supplies backend action evidence to interface C4. Interface C1 through C5 exit receipts remain owned by the separate interface plan and are not duplicated here.

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

### Phase `W02.P19` - Public operation contract and C0 dependency receipt

Publish the frontend-safe operation definition, atomic observation, REVIEW, and Workspace-refresh services, cut over current-only persistence, prove production composition, and mint the exact C0 dependency receipt before any visual operation projection begins.

- [x] `W02.P19.S115` - Extend the immutable operation registry with OperationSchemaIdentityV1, OperationPublicDefinitionContractV1, OperationPublicContractSetV1, exact strict-model fingerprints, registered REVIEW and refresh adapters, deterministic definition digests, and contract-set fixed-point validation; `src/cadrumo/application/operations/_registry.py`.
- [x] `W02.P19.S116` - Define the strict current-only operation observation, public projection, event-page, REVIEW-projection, response-control, cancellation, detach, and Workspace-refresh request, success, and typed refusal DTO families with independent V1 dispatch axes; `src/cadrumo/application/operations/_public.py`.
- [x] `W02.P19.S117` - Pin each definition_contract_digest atomically with invocation identity and define one application-owned observation materialization port binding the current snapshot, anchor cursor, bounded history, progress-fold input, and resynchronization checkpoint; `src/cadrumo/application/operations/_journal.py`.
- [x] `W02.P19.S118` - Implement the observation-read port over one locked journal-record read so snapshot, history page, progress checkpoint, replay status, and restart cursor share one authoritative anchor under interleaved transitions; `src/cadrumo/adapters/persistence/operations/_journal.py and src/cadrumo/adapters/persistence/operations/_journal_validation.py`.
- [x] `W02.P19.S119` - Implement the public observation service and deterministic progress fold with phase reset, independent lifecycle-terminal-effect projection, bounded cursor replay, cursor-ahead refusal, expiry or compaction resynchronization, detach, and reconnect semantics; `src/cadrumo/application/operations/_observation.py`.
- [x] `W02.P19.S120` - Implement registered safe REVIEW resolution and typed Workspace-refresh-target resolution with exact version, definition-digest, schema, expiry, terminal-state, and output validation while preserving separate response authority and rejecting caller-supplied result references; `src/cadrumo/application/operations/_projection_services.py`.
- [x] `W02.P19.S121` - Perform the PRE_RELEASE current-only cutover by proving zero affected nonterminal operations, refusing every superseded journal and lease shape, and deleting the v1 lease reader, acquisition migrator, retired schema dispatchers, fixtures, and migration tests without a compatibility path; `src/cadrumo/application/operations and src/cadrumo/adapters/persistence/operations`.
- [x] `W02.P19.S122` - Export the sole public operation contract family and compose the immutable production registry, observation, REVIEW, refresh, response, cancel, and detach services with real adapters through one import-light entrypoint seam consumed by CLI, MCP, and the later TUI launcher; `src/cadrumo/application/operations/__init__.py and src/cadrumo/entrypoints/_operation_composition.py`.
- [x] `W02.P19.S123` - Implement TuiOperationObservationDependencyReceiptV1 and its sole live-tree validator, proving strict round trips, atomic interleaving, progress and replay, registered REVIEW non-authority, restart refresh, digest drift refusal, production DI, sentinel non-retention, current-only deletion, and a semantic-plus-exact producer census that fails duplicate operation state or projection authorities; `src/cadrumo/application/operations/tests/test_public_operation_dependency_receipt.py`.
- [ ] `W02.P19.S124` - Produce the exact clean-commit C0 observation dependency receipt with accepted-parent and rejected-staging provenance, source ancestry, schema and capability inventories, contract digests, validator evidence, and the sole cohort-open disposition; `.vault/reference/2026-08-24-tui-operation-observation-dependency-receipt.md`.

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
- [x] `W03.P08.S40` - Register profile field mutation, repeatable-row mutation, bundle export, and profile logout operations through existing user-profile authorities; `src/cadrumo/application/user_profile/_operation_definitions.py`.
- [ ] `W03.P08.S41` - Move Google export planning and application orchestration out of the CLI frontend and register its external-effect operation; `src/cadrumo/application/export/_google_operation.py`.
- [x] `W03.P08.S42` - Expose authentication operation definitions through the authentication application facade; `src/cadrumo/application/auth/__init__.py`.
- [x] `W03.P08.S43` - Expose profile mutation and lifecycle operation definitions through the user-profile application facade; `src/cadrumo/application/user_profile/__init__.py`.
- [ ] `W03.P08.S44` - Expose Google export operation definitions through the export application facade; `src/cadrumo/application/export/__init__.py`.
- [ ] `W03.P08.S45` - Run every production-registered executor through the shared success, refusal, failure, interaction, cancellation-capability, deadline-capability, effect, and cleanup matrix and prove the exported definition population is complete; `src/cadrumo/application/operations/tests/test_registered_executor_conformance.py`.

### Phase `W03.P20` - Frontend-neutral Modelo Workspace V1

Implement the read-only Workspace V1 contract, stamped contributing ports, generated schema-field denominator, canonical owner projections, and live conformance without exposing registry grammar or duplicating ModeloWorkReview.

- [ ] `W03.P20.S125` - Define strict Workspace V1 version headers, visible and exact target admission, inspection and graded result arms, projection, bounded facets, schema and provenance records, capability and refusal families, locale summary, and safe read baseline without mutation authority; `src/cadrumo/application/modelo/_workspace_models.py`.
- [ ] `W03.P20.S126` - Define ModeloWorkspaceProducerContractV1, stamped contributing projections, owner-scoped ABA-safe epochs, atomic projection-plus-epoch ports, and the generated producer-contract inventory that rejects missing, duplicate, or stale contributors; `src/cadrumo/application/modelo/_workspace_producers.py`.
- [ ] `W03.P20.S127` - Generate the exhaustive registry model-and-field classification manifest from validated public schema types, classifying every reachable leaf and discriminator branch exactly once as projected, canonically derived, or backend-only with destination, owner, and bounded reason; `src/cadrumo/application/modelo/_workspace_manifest.py`.
- [ ] `W03.P20.S128` - Assemble Workspace projections only from stamped producer captures and canonical validated-registry, ModeloWorkReview, operator-state readiness, closure, calculation-revision, and source-graph owners, enforcing exact target admission, bounded materialization, two-pass epoch validation, locale selection, and stable safe-read baselines without parsing registry grammar; `src/cadrumo/application/modelo/_workspace_projection.py`.
- [ ] `W03.P20.S129` - Export the sole frontend-neutral Workspace request, projection, capability, refresh-target, refusal, and producer-contract family without exposing registry grammar or persistence types; `src/cadrumo/application/modelo/__init__.py`.
- [ ] `W03.P20.S130` - Prove strict Workspace round trips, exhaustive manifest coverage, exact ModeloWorkReview parity, readiness and closure parity, static versus graded admission, epoch and ABA refusal, locale behavior, bounded non-retention, forbidden-import boundaries, and a semantic-plus-exact census that fails duplicate Workspace authorities; `src/cadrumo/application/modelo/tests/test_workspace_projection.py`.
- [ ] `W03.P20.S131` - Implement the sole ModeloWorkspaceC2DependencyReceiptV1 validator with current-HEAD, accepted-authority, closed-predecessor, public-schema, producer-inventory, field-denominator, conformance, no-legacy, and redeclaration evidence checks while leaving receipt minting to the C1 handoff phase; `src/cadrumo/application/modelo/tests/test_workspace_dependency_receipt.py`.

### Phase `W03.P21` - Frontend-neutral Modelo Edit Contract V1

Implement edit admission, parsing, preflight, exact mutation baselines, typed scalar and row intents, guarded calculation persistence, mutation capability, and safe result receipts while leaving operation custody for the later C3 gate.

- [ ] `W03.P21.S132` - Define the strict ModeloEditContractV1 family covering version and compatibility headers, read-only edit schema, ModeloEditBaselineV1, parse and preflight requests and results, scalar and repeatable-row intents, guarded apply request, mutation capability, typed refusal, and immutable result receipt; `src/cadrumo/application/modelo/_edit_models.py`.
- [ ] `W03.P21.S133` - Implement edit admission, registry-backed schema projection, locale-neutral parsing, typed-intent normalization, and preflight services that issue exact ModeloEditBaselineV1 coordinates and never treat a Workspace safe-read baseline as mutation authority; `src/cadrumo/application/modelo/_edit_services.py`.
- [ ] `W03.P21.S134` - Persist encrypted Modelo edit result receipts with strict current-only serialization, compatibility-tuple validation, atomic lookup, and real round-trip evidence that cannot pass through tautological in-memory reconstruction; `src/cadrumo/adapters/persistence/profile/modelos_edit_receipts.py`.
- [ ] `W03.P21.S135` - Replace calculation-revision persistence with guarded work-and-calculation compare-and-swap so duplicate-existing and new-revision branches recheck the same edit baseline and co-commit immutable revision, work pointer, lifecycle event, and edit result receipt without any unguarded pointer advance; `src/cadrumo/application/modelo/_revision_persistence.py`.
- [ ] `W03.P21.S136` - Implement the application-owned edit executor that rechecks every ModeloEditBaselineV1 coordinate at the guarded commit point, refuses stale or incompatible intent without rebasing, delegates canonical calculation and guarded persistence, and returns only typed result receipts; `src/cadrumo/application/modelo/_edit_execution.py`.
- [ ] `W03.P21.S137` - Expose the edit facade and prove schema, parsing, preflight, scalar and row intent, guarded compare-and-swap, duplicate-result, rollback, compatibility refusal, persistence round-trip, non-retention, and redeclaration behavior while leaving operation-enrollment capability UNMEASURED until its C3 receipt exists; `src/cadrumo/application/modelo/__init__.py and src/cadrumo/application/modelo/tests/test_edit_contract.py`.
- [ ] `W03.P21.S138` - Implement the sole ModeloEditContractC3DependencyReceiptV1 validator with exact C2 predecessor, contract schema, baseline, guarded persistence, result-receipt, conformance, financial-handoff, production-definition, no-legacy, and redeclaration checks while leaving receipt minting to the C3 custody phase; `src/cadrumo/application/modelo/tests/test_edit_dependency_receipt.py`.

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
- [ ] `W04.P10.S104` - Relocate the sole Casilla review screen and tests to the canonical Modelo view as a read-only consumer of the existing public application.modelo ModeloWorkReview facade, preserve named-outlier evidence, delete the legacy inbound screen, facade exports, and locale references atomically without compatibility, and provide the migration evidence consumed by the interface C1 exit validator; `src/cadrumo/entrypoints/tui/modelo/view and src/cadrumo/adapters/inbound/tui/_modelo_work_review_screen.py`.
- [ ] `W04.P10.S58` - Move presentation tests under the canonical owning packages and remove backend imports of TUI test helpers; `src/cadrumo/entrypoints/tui/tests`.
- [ ] `W04.P10.S59` - Prove the relocation is behavior-preserving before any root app or navigation join is introduced; `src/cadrumo/entrypoints/tui/tests/test_relocation_parity.py`.

### Phase `W04.P22` - C1-to-C2 Workspace dependency handoff

Consume the green C1 interface exit, revalidate Workspace V1 and its producer fixed points on the same current tree, and mint the exact C2 dependency receipt that alone opens complex read-only consumers.

- [ ] `W04.P22.S139` - Run the sole Workspace dependency validator against the exact green ModeloWorkspaceC1ExitReceiptV1, accepted Workspace authorities, authoritative reconciliation, closed Workspace implementation tuple, generated producer and field inventories, current source tree, no-legacy proof, and duplicate-authority census; `src/cadrumo/application/modelo/tests/test_workspace_dependency_receipt.py`.
- [ ] `W04.P22.S140` - Produce and validate the exact clean-commit ModeloWorkspaceC2DependencyReceiptV1 binding the C1 predecessor digest, Workspace contract and producer fingerprints, captured epoch tuple, conformance evidence, current HEAD, and the exact C2 read destinations it opens; `.vault/reference/2026-08-24-tui-registry-api-gate-c2-dependency-receipt.md`.

## Wave `W05` - TUI operation projection and review

Build the operation-agnostic modal, live log projection, interactions, and domain review views solely as consumers of supervisor state.

### Phase `W05.P11` - Generic operation projection

Project supervisor snapshots and ordered events into a detachable modal, live logs, progress, controls, and typed interactions.

- [ ] `W05.P11.S60` - Implement a TUI controller limited to the composed public submit, atomic observation, registered REVIEW, typed response, cancel, detach, and Workspace-refresh services, with no supervisor inspection or persistence access; `src/cadrumo/entrypoints/tui/operations/controller.py`.
- [ ] `W05.P11.S61` - Project only OperationPublicProjectionV1 and its public capability and refusal fields into immutable modal view models without importing persisted snapshots, journal records, or supervisor-private state; `src/cadrumo/entrypoints/tui/operations/projection.py`.
- [ ] `W05.P11.S62` - Project only OperationPublicEventPageV1 into bounded live and historical log views, honoring public cursors, replay and resynchronization dispositions, and approved diagnostic references without reading the journal; `src/cadrumo/entrypoints/tui/operations/logs.py`.
- [ ] `W05.P11.S63` - Render only registered safe REVIEW projections and separately response-authorized APPLY and REJECT controls, treating public INPUT and CHOICE interaction kinds as unsupported until a later accepted contract enrolls them; `src/cadrumo/entrypoints/tui/operations/interactions.py`.
- [ ] `W05.P11.S64` - Implement the generic detachable operation modal solely from public projection, event-page, REVIEW, response-control, cancellation, detach, terminal-receipt, and typed Workspace-refresh DTOs; `src/cadrumo/entrypoints/tui/operations/modal.py`.
- [ ] `W05.P11.S65` - Expose a narrow operation-presentation facade that accepts only public operation contracts and exports neither Textual internals nor application-private operation types as backend contracts; `src/cadrumo/entrypoints/tui/operations/__init__.py`.
- [ ] `W05.P11.S66` - Derive spinner visibility, enabled controls, close policy, interaction affordance, and terminal copy solely from OperationPublicProjectionV1 and public response-control projections without reclassifying lifecycle truth; `src/cadrumo/entrypoints/tui/operations/projection.py`.
- [ ] `W05.P11.S67` - Prove public cursor replay, resynchronization, detach and reattach, REVIEW revision and response authority, cancellation acknowledgement, typed Workspace refresh, terminal settlement, log visibility, subscriber loss, and exact C0 receipt ancestry with no private operation imports; `src/cadrumo/entrypoints/tui/operations/tests`.

### Phase `W05.P12` - Domain review projections

Render census field review and filed-history outcome detail without placing domain merge or effect policy in the TUI.

- [ ] `W05.P12.S68` - Implement census local-versus-persisted field review with suggested intent, per-field selection, apply all, reject, and stale-proposal display; `src/cadrumo/entrypoints/tui/profile/sync_review.py`.
- [ ] `W05.P12.S69` - Implement filed-history stage, unit, refusal, partial-effect, evidence, wallet, notification, and provenance result projection; `src/cadrumo/entrypoints/tui/profile/sync_review.py`.
- [ ] `W05.P12.S70` - Prove census review dispatches exact typed responses and never writes or recomputes policy in the TUI; `src/cadrumo/entrypoints/tui/profile/tests/test_census_sync_review.py`.
- [ ] `W05.P12.S71` - Prove filed-history progress, scoped errors, viewable logs, child provenance, and partial outcomes remain visible through settlement; `src/cadrumo/entrypoints/tui/profile/tests/test_filed_history_operation_view.py`.

### Phase `W05.P23` - C3 transient financial custody and dependency receipts

Add the distinct transient financial operand protocol, enroll the Modelo calculation edit, prove crash-safe custody and atomic effect evidence, and mint the financial-operand and Edit Contract C3 dependency receipts without treating either as a visual exit.

- [ ] `W05.P23.S141` - Define OperationTransientFinancialOperandProtocolV1 with typed declaration, requirement, submission, access-grant, delivery, acknowledgement, release, expiry, refusal, and broker contracts that are distinct from EphemeralSecretSubmission and persistent secure-reference flows and prohibit operand hashing or durable derivatives; `src/cadrumo/application/operations/_financial_operand.py`.
- [ ] `W05.P23.S142` - Persist only non-sensitive custody checkpoints and serialize awaiting_submission to bound to delivery_started to delivery_acknowledged to released transitions with expiry, cancellation, terminal settlement, crash classification, restart reconciliation, and exactly-once release across racing supervisor paths; `src/cadrumo/application/operations/_journal.py, src/cadrumo/application/operations/_supervisor.py, and src/cadrumo/adapters/persistence/operations/_journal_validation.py`.
- [ ] `W05.P23.S143` - Extend registered operation definitions with validated transient-financial-operand declarations and an effect-receipt resolver that narrows recorded mutation, interruption, and uncertain-effect claims from committed application evidence without exposing financial operand material; `src/cadrumo/application/operations/_registry.py`.
- [ ] `W05.P23.S144` - Enroll the calculate and recalculate edit family through ModeloEditContractV1 and the transient financial operand handoff, register the typed ModeloWorkspaceRefreshTargetV1 resolver, and ensure frontend entrypoints can submit only typed requests without custody or mutation access; `src/cadrumo/application/modelo/_operation_definitions.py`.
- [ ] `W05.P23.S145` - Prove strict protocol round trips, successful delivery, expiry and cancellation races, crash windows, restart classification, exactly-once release, sentinel non-retention, guarded edit compare-and-swap, effect-receipt narrowing, immutable production composition, and a semantic-plus-exact census that fails duplicate custody or edit authorities; `src/cadrumo/application/operations/tests/test_financial_operand_conformance.py and src/cadrumo/application/modelo/tests/test_edit_operation_conformance.py`.
- [ ] `W05.P23.S146` - Implement the sole TuiOperationFinancialOperandDependencyReceiptV1 validator with accepted-authority, protocol-schema, custody-transition, crash, effect, production-composition, non-retention, current-only, no-legacy, and duplicate-authority evidence checks; `src/cadrumo/application/operations/tests/test_financial_operand_dependency_receipt.py`.
- [ ] `W05.P23.S147` - Produce and validate the exact clean-commit TuiOperationFinancialOperandDependencyReceiptV1 with protocol and schema fingerprints, custody-state evidence, crash matrix, non-retention proof, production definition inventory, source ancestry, and the precise edit path it opens; `.vault/reference/2026-08-24-tui-operation-financial-operand-dependency-receipt.md`.
- [ ] `W05.P23.S148` - Run the sole Edit Contract dependency validator against the exact green Workspace C2 and financial-operand receipts, accepted edit authority, closed EditContract implementation tuple, enrolled production definition, guarded result evidence, current source tree, no-legacy proof, and duplicate-authority census; `src/cadrumo/application/modelo/tests/test_edit_dependency_receipt.py`.
- [ ] `W05.P23.S149` - Produce and validate the exact clean-commit ModeloEditContractC3DependencyReceiptV1 binding the Workspace C2 and financial-operand predecessor digests, edit compatibility tuple, baseline and surface fingerprints, guarded persistence evidence, result schema, production definition, conformance, and exact C3 edit destinations it opens; `.vault/reference/2026-08-24-modelo-edit-contract-c3-dependency-receipt.md`.

## Wave `W06` - Composition cutover and legacy deletion

Join the independently green backend and frontend lanes, migrate every reverse consumer, switch packaging, and remove the legacy adapter package.

### Phase `W06.P24` - C4 Modelo lifecycle operation enrollment

Enroll rename, discard, verify, local file, export, and amend one by one through their existing application writers, each with an independently proven capability, interaction, effect receipt, and typed Workspace refresh result.

- [ ] `W06.P24.S150` - Enroll modelo.work.rename through the existing rename_work_unit single writer with exact approval and capability rules, declared atomic write set, safe effect and result receipt, and typed Workspace refresh target without recreating lifecycle policy; `src/cadrumo/application/modelo/_operation_definitions.py and src/cadrumo/application/modelo/_work_lifecycle.py`.
- [ ] `W06.P24.S151` - Enroll modelo.work.discard through the existing discard_work_unit single writer with exact destructive approval, no-effect refusal, declared atomic write set, safe effect receipt, and typed selection refresh target without recreating lifecycle policy; `src/cadrumo/application/modelo/_operation_definitions.py and src/cadrumo/application/modelo/_work_lifecycle.py`.
- [ ] `W06.P24.S152` - Enroll modelo.work.verify through the existing verify_modelo_revision authority with exact capability evidence, progress and REVIEW declarations, guarded persistence and event effects, safe result receipt, and typed Workspace refresh target; `src/cadrumo/application/modelo/_operation_definitions.py and src/cadrumo/application/modelo/_verification_actions.py`.
- [ ] `W06.P24.S153` - Enroll modelo.work.file through the existing file_modelo_revision authority as local filing and human handoff only, with precondition refusal, exact approval, atomic filing effects, safe result receipt, and typed Workspace refresh target; `src/cadrumo/application/modelo/_operation_definitions.py and src/cadrumo/application/modelo/_filing_actions.py`.
- [ ] `W06.P24.S154` - Enroll canonical modelo.export through the existing export_modelo_revision authority with capability and identity preconditions, transient output custody, safe effect/result evidence, and no remote AEAT submission or duplicate export writer; `src/cadrumo/application/modelo/_operation_definitions.py and src/cadrumo/application/modelo/_export.py`.
- [ ] `W06.P24.S155` - Enroll modelo.work.amend through the existing amend_modelo_revision authority as the sole C4 amendment mutation, with baseline evidence, amendment-kind REVIEW, atomic catalogue/event effects, safe result receipt, typed Workspace refresh target, and an explicit amend-wizard denominator disposition; `src/cadrumo/application/modelo/_operation_definitions.py and src/cadrumo/application/modelo/_amendment_actions.py`.
- [ ] `W06.P24.S156` - Prove the generated C4 action denominator and every enrolled lifecycle definition against canonical capability owners, exact interactions, single writers, effect receipts, refresh adapters, refusal behavior, non-retention, and semantic-plus-exact redeclaration census before any action becomes available; `src/cadrumo/application/modelo/tests/test_lifecycle_operation_conformance.py`.

### Phase `W06.P13` - Root composition and packaging

Compose the independently green lanes in the TUI launcher and app, then expose the dedicated installed entrypoint.

- [ ] `W06.P13.S72` - Compose every exported operation definition into one immutable production registry with concrete operation adapters, journals, resources, and the supervisor in the sole TUI composition root; `src/cadrumo/entrypoints/tui/launcher.py`.
- [ ] `W06.P13.S73` - Join profile, secret, flow, operation, and Modelo areas through navigation only after their exact receipts are green, composing the one closed Modelo route/action factory catalogue and keeping every non-green cohort unmounted; `src/cadrumo/entrypoints/tui/app.py`.
- [ ] `W06.P13.S74` - Delegate module execution directly to the TUI launcher without importing the CLI; `src/cadrumo/entrypoints/tui/__main__.py`.
- [ ] `W06.P13.S75` - Add the dedicated installed TUI console entry point targeting the launcher directly; `pyproject.toml`.

### Phase `W06.P14` - Reverse-consumer migration

Replace every CLI, application-test, and development import of the legacy TUI with backend facades or out-of-process invocation.

- [ ] `W06.P14.S76` - Remove frontend-owned manager callbacks and consume registered operation APIs and application results only; `src/cadrumo/entrypoints/cli/_config/_manager_actions.py`.
- [ ] `W06.P14.S157` - Replace the direct CLI profile-logout execution door with the composed public operation API and delete its application-authority call path without a compatibility branch; `src/cadrumo/entrypoints/cli/_config/_custody.py and focused CLI operation-projection tests`.
- [ ] `W06.P14.S158` - Delete remaining ad-hoc canonical JSON and SHA-256 redeclarations in operation-adjacent flow and filing paths by preserving their domain payload normalization while routing digest mechanics exclusively through core.hashing, with byte-parity and semantic RAG fixed-point tests; `src/cadrumo/application/flows/_definition.py and src/cadrumo/application/filing/_review.py`.
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

The discharged `casilla-schema` prerequisite no longer blocks execution. Independent backend contract phases may proceed in parallel when they do not share an authority or write surface, but receipt minting, composition, cutover, and deletion remain serialized. No TUI operation projection begins before the exact C0 receipt. Interface C2 waits for its exact Workspace C2 dependency receipt, interface C3 waits for the exact C2 exit plus financial-operand and Edit Contract dependency receipts, interface C4 waits for the C3 exit plus the enrolled action denominator, and C5 waits for the C4 exit and final structural fixed point. The interface plan consumes these receipts and never redeclares their application contracts.

## Verification

The plan is complete when every Step is closed, the four sole dependency validators for public operation observation, Workspace C2, transient financial operands, and Edit C3 pass against their exact current-HEAD artifacts, and the operation conformance matrix proves honest success, refusal, failure, cancellation, timeout, interruption, effect, cleanup, and restart settlement. Workspace and Edit proof must cover strict public-schema manifests, stamped producer epochs, exact canonical-owner parity, guarded compare-and-swap, safe result receipts, production dependency injection, non-retention, and semantic-plus-exact producer censuses that fail any competing authority. Structural closure additionally requires current-only operation persistence with no legacy reader or migrator, no Textual or TUI implementation outside `cadrumo.entrypoints.tui`, no outside Python import of that package, no direct TUI mutation callback, deletion of `cadrumo.adapters.inbound.tui` without a compatibility facade, and installed TUI proof at supported terminal sizes.
