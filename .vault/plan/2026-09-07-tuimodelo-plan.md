---
tags:
  - '#plan'
  - '#tuimodelo'
date: '2026-09-07'
tier: L3
related:
  - '[[2026-09-07-tuimodelo-reference]]'
  - '[[2026-09-07-tuimodelo-form-projection-adr]]'
  - '[[2026-09-07-tuimodelo-filing-lifecycle-adr]]'
  - '[[2026-09-07-tuimodelo-reconcile-verify-adr]]'
  - '[[2026-09-07-tuimodelo-export-destinations-adr]]'
  - '[[2026-09-07-tuimodelo-work-creator-adr]]'
  - '[[2026-09-07-tuimodelo-satellite-families-adr]]'
modified: '2026-09-07'
body_schema: body-v2
body_hash: 'sha256:c52b1dbbbef3a1720bec44efbc582fe5c7a0cc56c4d8c2e286f349cd5bff8ed6'
  - "[[2026-09-07-tuimodelo-adapter-migration-adr]]"
---

# `tuimodelo` plan

## Description

Deliver the modelo declaration interface as a reachable product surface. The centre of gravity
is joining capability that already exists rather than authoring new screens: six workspace
destinations are built and only one is reachable, six action request builders have no production
caller, the edit session's submit path is never called, and two of the twenty registered
operations are reachable from a full-screen surface. Seventy-seven of the seventy-nine
classified modelo actions are pending.

The ordering is forced rather than chosen, though not in the way a first reading suggested.
Session authorization already works for a full-screen surface; what is stranded is the capability
declaration, which sits inside the command-line package that the frontend is forbidden to import,
and which the admission gate itself must read. That relocation therefore precedes the gate.
Nothing can be generated until presentation has a declared ordering, because the registry carries
none and offsets place barely a third of the corpus. Reachability is several gaps rather than
one: five destinations resolve nowhere, the editor and history are not members of the closed
destination alias at all, and the action screens are referenced only from tests.

Two families that read as peripheral are inside the core loop and are scheduled accordingly: the
carry-forward wallet, whose gate blocks the most-used modelo from being calculated, verified,
filed or exported pending an override with no surface, and the aggregation write path, which is
the only way an operator enters calculation inputs for four withholding modelos.

## Steps

## Wave `W01` - governance hygiene and admission gate

Clear the governance debt that blocks every later wave. A dead campaign still holds seven rows of the tui-architecture plan open against a gate that can never close, two tui-interface rows describe a retired mechanism, and the action denominator cannot yet prove admission because its drift check never observes a disposition or an interface capability. Nothing downstream can be scheduled honestly until scope is annotated, holds are adjudicated and the gate can fail in both directions.

### Phase `W01.P01` - adjudicate inherited holds

Resolve the rows an archived campaign left held and the rows whose subject a later decision retired, so annotation can proceed without layering a second claim over a dead one.

- [ ] `W01.P01.S01` - Adjudicate the seven displaced-and-held rows against a gate whose owning campaign is archived, recording a disposition and a reason for each; `.vault/plan/2026-08-11-tui-architecture-plan.md`.
- [ ] `W01.P01.S02` - Adjudicate as superseded the two rows whose subject the accepted interface decision retired, citing the retirement commit rather than completing or deleting them; `.vault/plan/2026-08-11-tui-interface-plan.md`.
- [ ] `W01.P01.S03` - Close the action-denominator row on its standing gate and correct the execution record that asserts a deleted snapshot document; `.vault/plan/2026-08-11-tui-interface-plan.md`.

### Phase `W01.P02` - make the denominator an admission gate

Extend the denominator so a delivered surface and its recorded classification must agree, and correct the specs that under-declare their write route.

- [ ] `W01.P02.S04` - Extend the observed action signature with interface capability and dispatchability so the gate can see a wired surface; `dev/quality/modelo_workspace_action_denominator.py`.
- [ ] `W01.P02.S05` - Add delivered dispositions for reads and for mutations to the closed taxonomy, which today offers no arm a delivered mutation can occupy; `dev/quality/modelo_workspace_action_denominator.py`.
- [ ] `W01.P02.S06` - Red the gate when a recorded disposition contradicts the observed shape, applying the rule to the command-graph and dispatch intersection only; `dev/quality/modelo_workspace_action_denominator.py`.
- [ ] `W01.P02.S07` - Correct the two review-package specs that declare no write route while carrying local-state side effects and emitting events; `src/cadrumo/entrypoints/cli`.

### Phase `W01.P03` - record campaign scope and outstanding decisions

Annotate absorbed rows with their new owner, publish the coverage baseline, and author the two migration decisions the adapter wave depends on.

- [ ] `W01.P03.S08` - Annotate each of the 25 open rows in the two source plans with its disposition here or its retention there, naming every row rather than referring to them collectively; `.vault/plan`.
- [ ] `W01.P03.S09` - Correct the stale reopening condition that cites a retired receipt mechanism; `src/cadrumo/application/modelo/_edit_facade.py`.
- [ ] `W01.P03.S10` - Author the lifecycle-vocabulary decision reconciling the adapter-derived work-unit state with the frontend lifecycle kind; `.vault/adr`.
- [ ] `W01.P03.S11` - Author the capability-model decision placing the authorization and capability model outside the command-line package; `.vault/adr`.
- [ ] `W01.P03.S12` - Publish the campaign coverage baseline as a standing artefact derived from the denominator; `dev/quality`.
- [ ] `W01.P03.S141` - Reopen the edit capability projection under the surviving mechanism, replacing the retired condition it still cites, since every editor step routes through a seam nothing currently opens; `src/cadrumo/application/modelo/_edit_facade.py`.
- [ ] `W01.P03.S142` - Relocate the capability projection out of the private underscore module to a public defining module, because a frontend import of it is otherwise forbidden by the architecture boundary; `src/cadrumo/application/modelo`.
- [ ] `W01.P03.S128` - Open the sibling adapter-purity campaign for the residual violations this campaign does not take: 159 identified in total, roughly 40 here, leaving about 120 across the ledger, configuration and live lanes, and record that the ledger lane's prior owner is archived so the work is not orphaned twice; `.vault`.

## Wave `W02` - adapter to backend migration

Make both adapters pure consumers OF THE MODELO LANE. This wave does not make the command line a pure consumer overall: 159 adapter-boundary violations are identified across four lanes and this wave takes roughly 40 of them - the modelo lane, the shared capability declaration, and the frontend's own duplicate wiring. The residual 62 ledger, 52 configuration and 26 live rows belong to the sibling campaign recorded in W01. Session authorization already works for a full-screen surface and is not the blocker an earlier reading suggested; what is stranded is the capability declaration, which both adapters need and only one can reach.

### Phase `W02.P04` - authorization floor

Share the capability declaration both adapters need. The frontend already authorizes a session and admits per surface without any verb path, so authorization is not the blocker; the capability posture is, because it is declared inside the command-line package and the frontend is forbidden by import contract from reaching it.

- [ ] `W02.P04.S13` - Share the interface capability declaration out of the command-line package so a full-screen surface can read a command's capability posture without importing the adapter; `src/cadrumo/entrypoints/cli/command_spec.py`.
- [ ] `W02.P04.S14` - Relocate the capability model to a shared owner both adapters may consume, sequencing it before the denominator extension that reads it; `src/cadrumo/entrypoints/cli/command_spec.py`.
- [ ] `W02.P04.S15` - Prove the per-surface admission path refuses and admits correctly for a modelo destination, since session authorization already works without a verb path and needs no change; `src/cadrumo/entrypoints/tui/launcher.py`.

### Phase `W02.P05` - relocate blocking read policy

Give history, casilla visibility, effective lifecycle state and cross-modelo binding queries application owners, so a second surface can call them instead of reimplementing them.

- [ ] `W02.P05.S16` - Give modelo history an application service owning the event taxonomy, filing-year fallback, filtering and ordering the handler holds today; `src/cadrumo/application/modelo/history.py`.
- [ ] `W02.P05.S17` - Reconcile the relocated history vocabulary with the frontend lifecycle kind under the lifecycle-vocabulary decision; `src/cadrumo/application/modelo`.
- [ ] `W02.P05.S18` - Move casilla visibility and effective work-unit state derivation out of the payload renderer into the application layer; `src/cadrumo/entrypoints/cli/_modelo_rendering.py`.
- [ ] `W02.P05.S19` - Give the cross-modelo binding query an application owner that refuses rather than silently dropping modelos that fail; `src/cadrumo/application/modelo/binding_resolution.py`.
- [ ] `W02.P05.S20` - Adjudicate the history model module rather than deleting it: it has no production writer but is imported by the custody-carry resolver, so establish whether it is retired with a custody migration or kept and typed; `src/cadrumo/application/filing/history_models.py`.

### Phase `W02.P06` - relocate blocking mutation and legal policy

Move override admissibility, the detail-row grammar with its intracommunity rule, the aggregation write path, amendability, the spreadsheet staleness refusal and review-package assembly into the application layer.

- [ ] `W02.P06.S21` - Move override admissibility out of the binding-resolve handler onto the same lock set the engine uses; `src/cadrumo/application/modelo/binding_resolution.py`.
- [ ] `W02.P06.S22` - Relocate the detail-row vocabulary, row-class dispatch and decimal classification, and relocate the intracommunity country-prefix rule only once its governing provision is cited, since it is filing-grade law currently carrying no authority reference; `src/cadrumo/application/modelo`.
- [ ] `W02.P06.S23` - Move the aggregation write path off its adapter-resident modelo branch tree into a typed application use case; `src/cadrumo/application/aggregation`.
- [ ] `W02.P06.S24` - Relocate the amendability rule and remove the re-declared evidence gate from the amendment wizard; `src/cadrumo/application/modelo/amendment_actions.py`.
- [ ] `W02.P06.S25` - Give the spreadsheet round trip an application service and move its staleness refusal off the outbound adapter call; `src/cadrumo/application/storage/calc_sheets`.
- [ ] `W02.P06.S26` - Extract review-package assembly, including its temporary-file lifecycle, into an application use case; `src/cadrumo/application/modelo`.

### Phase `W02.P07` - close correctness divergences

Collapse duplicated election defaults, remove coerced zeroes and hardcoded availability, and give each use case its own repository defaults.

- [ ] `W02.P07.S27` - Collapse the filing-election defaults spelled in four adapter files onto the single application declaration; `src/cadrumo/application/modelo`.
- [ ] `W02.P07.S28` - Remove the coerced zero for missing scenario values in spreadsheet verification; `src/cadrumo/application/storage/calc_sheets`.
- [ ] `W02.P07.S29` - Restore the five-state availability model on the overview evidence path that hardcodes availability; `src/cadrumo/entrypoints/cli/_overview_evidence.py`.
- [ ] `W02.P07.S30` - Move idempotency classification and advisory selection for verify and file into the application layer; `src/cadrumo/application/modelo/filing_actions.py`.
- [ ] `W02.P07.S31` - Give each modelo application use case its own repository defaults, following the pattern the history service already sets; `src/cadrumo/application/modelo`.
- [ ] `W02.P07.S32` - Move ledger period-token applicability out of the adapter parser onto the period model; `src/cadrumo/core/period.py`.
- [ ] `W02.P07.S149` - Author the adapter-purity detector that fails when policy moves back into an adapter, which this wave's closure condition requires and no step currently provides; `dev/quality`.

### Phase `W02.P08` - remove adapter duplication

Delete the duplicated work-review composition and the frontend persistence imports, and migrate the two command-resident importers.

- [ ] `W02.P08.S33` - Delete the duplicated work-review composition so both adapters call one service; `src/cadrumo/entrypoints/tui/launcher.py`.
- [ ] `W02.P08.S34` - Remove the frontend persistence imports the composition root carries; `src/cadrumo/entrypoints/tui/launcher.py`.
- [ ] `W02.P08.S35` - Migrate the borrador import out of its handler into an application service; `src/cadrumo/application/live`.
- [ ] `W02.P08.S36` - Migrate the census certificate import out of its transport handler, and record that its parser refuses unconditionally today; `src/cadrumo/application/user_profile`.

## Wave `W03` - declared form projection

Give every generated surface an ordering, a grouping and an honest coverage number. Fix the three value-handling defects that would otherwise ship an editor accepting arbitrary text into identity fields, then define the declaration, build the generator over official sources, and gate coverage and cross-revision stability.

### Phase `W03.P09` - value-handling prerequisites

Fix per-type parsing, construct the unsupported-kind refusal, and route labels through the continuity tier before any generated surface is editable.

- [ ] `W03.P09.S37` - Give the scalar parser a real typed arm for each of the twelve data types that currently return raw text; `src/cadrumo/application/modelo/edit_services.py`.
- [ ] `W03.P09.S38` - Construct the declared unsupported-kind refusal so an unsupported field renders a refusal view rather than a text box; `src/cadrumo/application/modelo/edit_models.py`.
- [ ] `W03.P09.S39` - Route workspace label resolution through the continuity tier instead of the occurrence key alone; `src/cadrumo/application/modelo/workspace.py`.
- [ ] `W03.P09.S40` - Surface the untranslated-fallback disposition rather than returning a source-language string silently; `src/cadrumo/application/modelo/workspace.py`.

### Phase `W03.P10` - declaration format and generator

Define the presentation declaration and generate it from export offsets and the official record-design corpus, reviewed before publication.

- [ ] `W03.P10.S41` - Define the presentation declaration: an ordered page and section tree, a placement per casilla with an explicit unplaced arm carrying a reason, an official heading per node, and row groups with cardinality; `src/cadrumo/domain/calculations/registry`.
- [ ] `W03.P10.S42` - Build the development-time generator seeding order from export field offsets within record order and headings from the official record-design corpus; `dev/registry`.
- [ ] `W03.P10.S43` - Publish and load the declaration through the validated registry authority, compiled and validated with the revision it describes; `src/cadrumo/domain/calculations/registry/authority.py`.
- [ ] `W03.P10.S44` - Give the declaration a cache identity that includes the source state it was generated from; `src/cadrumo/domain/calculations/registry/loader_cache.py`.
- [ ] `W03.P10.S45` - Review each generated declaration before publication, smallest fixed-width modelos first; `src/cadrumo/_data/registry`.
- [ ] `W03.P10.S153` - Enrol a validator for the new declaration family in the registry dispatch, since a declaration family without one cannot fail closed; `src/cadrumo/domain/calculations/registry`.

### Phase `W03.P11` - modelo 100 seed

Seed the flagship consumer form from the RentaWeb dictionary through the existing dictionary-override mechanism, into the same declaration format.

- [ ] `W03.P11.S46` - Seed modelo 100 from the RentaWeb dictionary and schema path tree through the existing dictionary-override mechanism, into the same declaration format; `dev/registry`.
- [ ] `W03.P11.S47` - Record the projection source on the read model so it cannot switch silently between revisions of one modelo; `src/cadrumo/application/modelo/workspace_models.py`.

### Phase `W03.P12` - structural cases

Declare row groups, resolve multi-position casillas, and correct the registry sections that break contiguity.

- [ ] `W03.P12.S48` - Declare the rectangular slotted tables and the recoverable row families as typed row groups rather than per-slot scalars; `src/cadrumo/domain/calculations/registry`.
- [ ] `W03.P12.S49` - Introduce the row-group type the frontend does not yet reference and render it; `src/cadrumo/entrypoints/tui/modelo/edit`.
- [ ] `W03.P12.S50` - Give multi-position casillas a primary placement and declared aliases so one value is edited in one place; `src/cadrumo/domain/calculations/registry`.
- [ ] `W03.P12.S51` - Correct the registry sections that misplace recargo boxes and break section contiguity, citing the official record design that establishes the correct placement; `src/cadrumo/_data/registry`.

### Phase `W03.P13` - coverage and stability gates

Publish declared and placed coverage, diff declarations across revisions, and extend the accepted read model rather than adding a second one.

- [ ] `W03.P13.S52` - Publish a coverage gate reporting declared against undeclared revisions and placed against unplaced casillas; `dev/quality`.
- [ ] `W03.P13.S53` - Gate cross-revision stability by diffing a declaration against its predecessor and requiring a reviewed acknowledgement when placements move; `dev/quality`.
- [ ] `W03.P13.S54` - Extend the accepted work review read model with the projection rather than introducing a second read model; `src/cadrumo/application/modelo/workspace_models.py`.
- [ ] `W03.P13.S55` - Resolve an undeclared revision to an inspection-only projection that states why it is not editable; `src/cadrumo/application/modelo/workspace.py`.
- [ ] `W03.P13.S56` - Re-measure the ordering fidelity claim against the official record design and record the reproducible figure; `dev/registry`.
- [ ] `W03.P13.S148` - Measure the casilla-to-official-description join rate and record the reproducible figure, which the verification section demands and no other step provides; `dev/registry`.

## Wave `W04` - the reachability join

Turn built-but-unreachable capability into reachable capability. One missing navigation mechanism keeps history, the editor, verification and every action surface unreachable at once; supervision keeps the mutations outside the operation registry. This wave is where the campaign's existing investment starts returning.

### Phase `W04.P14` - inter-destination navigation

Give the modelo workspace a way to move between its own destinations and to carry a selection, under the accepted host placements.

- [ ] `W04.P14.S57` - Give the modelo workspace inter-destination navigation, which no destination currently offers; `src/cadrumo/entrypoints/tui/modelo/routes.py`.
- [ ] `W04.P14.S58` - Carry a work-unit selection past the selection terminus that currently ends the flow; `src/cadrumo/entrypoints/tui/modelo/view/controller.py`.
- [ ] `W04.P14.S59` - Adopt the accepted host placements, keeping history under declarations and reconciliation under the authority-sync workspace; `src/cadrumo/entrypoints/tui`.
- [ ] `W04.P14.S60` - Extend the modelo workspace in place under declarations rather than promoting it to a shell destination; `src/cadrumo/entrypoints/tui/modelo/view/models.py`.
- [ ] `W04.P14.S143` - Admit the editor and history destinations into the closed destination alias, which does not currently contain them; `src/cadrumo/entrypoints/tui/modelo/routes.py`.
- [ ] `W04.P14.S144` - Wire an action affordance so the six action screens are reachable by an operator rather than only from tests; `src/cadrumo/entrypoints/tui/modelo/actions.py`.

### Phase `W04.P15` - operation supervision

Bring the modelo action family under the supervisor and thread the elections the frontend operation currently drops.

- [ ] `W04.P15.S61` - Register operations for the modelo action identities that have none, working through the 25 the unregistered-operations tuple names, updating the dispatch table and the fixed-point authority atomically with each; `src/cadrumo/application/modelo/operation_definitions.py`.
- [ ] `W04.P15.S62` - Thread the refund, payment, prior-domiciliation and product-identity elections through the export operation so both adapters emit the same declaration type; `src/cadrumo/application/modelo/operation_definitions.py`.
- [ ] `W04.P15.S63` - Route modelo mutations through the host operation modal rather than submitting inline; `src/cadrumo/entrypoints/tui/modelo/action`.
- [ ] `W04.P15.S64` - Register an operation for calculation, which the reconcile and projection surfaces both depend on; `src/cadrumo/application/modelo/operation_definitions.py`.
- [ ] `W04.P15.S151` - Update the frontend dispatch table and the unregistered-operations authority together with each registration, since the fixed-point test pins both as canonical; `src/cadrumo/entrypoints/tui/modelo/actions.py`.

### Phase `W04.P16` - unstub and instrument

Populate the filing-history and evidence zones the frontend hardcodes as unavailable, and wire the modelo fixtures the harness cannot currently drive.

- [ ] `W04.P16.S65` - Populate the filing-history zone the workbench generation hardcodes as unavailable, using the merge helper that already exists; `src/cadrumo/application/workbench_generation.py`.
- [ ] `W04.P16.S66` - Populate the authority evidence axis the workbench generation hardcodes as never captured; `src/cadrumo/application/workbench_generation.py`.
- [ ] `W04.P16.S67` - Wire the modelo fixtures into the devtools harness so the modelo destinations become drivable; `src/cadrumo/entrypoints/tui/devtools/modelo_fixtures.py`.
- [ ] `W04.P16.S68` - Enrol the modelo destinations in the visual-verification surface list and the coverage classification; `dev/tui`.
- [ ] `W04.P16.S145` - Author the four-locale catalogue entries every new surface in this campaign requires, with real translations rather than key echoes; `src/cadrumo/locales`.
- [ ] `W04.P16.S146` - Add a coverage classification entry for every full-screen class this campaign introduces, and sequence it so no surface lands unclassified; `dev/tui/_coverage.py`.
- [ ] `W04.P16.S147` - Enrol each new surface in the visual-verification surface list and the devtools surface catalogue; `dev/tui`.

### Phase `W04.P32` - filing history and lifecycle presentation

Deliver the decision the filing-lifecycle record makes, which no other phase schedules. Its prerequisites are wired elsewhere in this wave; the presentation itself - three axes never merged, the obligation axis as the sole origin of a missed declaration, the next-action cell, sealed-revision display, amendment kind with its legal basis - has no home without this phase, and without it the campaign ships no history surface.

- [ ] `W04.P32.S129` - Present the local filing axis and the authority submission axis as two columns that are never merged, so a local mark can never read as authority acceptance; `src/cadrumo/entrypoints/tui/declarations`.
- [ ] `W04.P32.S130` - Derive the missed and upcoming states from the obligation axis, which is where they live, joining record and calendar projections by natural filing address; `src/cadrumo/application/modelo/declarations_workspace.py`.
- [ ] `W04.P32.S131` - Render the next-action cell from the existing blocker-to-operator-action projection rather than from a status string; `src/cadrumo/entrypoints/tui/declarations`.
- [ ] `W04.P32.S132` - Display revision state through the current-sealed state set so a superseded revision never renders as current; `src/cadrumo/entrypoints/tui/declarations/revisions.py`.
- [ ] `W04.P32.S133` - Disclose amendment kind with the legal basis governing it, since the three kinds carry different operator consequences; `src/cadrumo/entrypoints/tui/declarations/filing_history.py`.
- [ ] `W04.P32.S134` - Present filing as the two-part act it is, and discard as terminal and rename as cosmetic, matching the lifecycle the domain enforces; `src/cadrumo/entrypoints/tui/modelo/action`.
- [ ] `W04.P32.S135` - Record the money-column deferral on the surface as a data gap, not a privacy one; `src/cadrumo/entrypoints/tui/declarations/filing_history.py`.
- [ ] `W04.P32.S136` - Surface the filing-record and verification-report reads that no other step covers, listing and viewing each; `src/cadrumo/entrypoints/tui/declarations`.
- [ ] `W04.P32.S137` - Surface the work status, revision and revisions reads against the sealed-state display rule; `src/cadrumo/entrypoints/tui/modelo/view`.
- [ ] `W04.P32.S138` - Surface the workflow run reads and the resume affordance, or record them command-line only with a reason; `src/cadrumo/entrypoints/tui/modelo/view`.
- [ ] `W04.P32.S139` - Surface the work dependencies read against the cross-period blocker projection; `src/cadrumo/entrypoints/tui/modelo/view/overview.py`.
- [ ] `W04.P32.S140` - Dispose of the maritime exemption preview and the taxation comparison explicitly rather than leaving them unadjudicated; `dev/quality/modelo_workspace_action_denominator.py`.

## Wave `W05` - editing and calculation inputs

Deliver the casilla editor over the admission seam that already exists, including the repeated-row surface that detail-row modelos have never had, and the observation-entry surface that four withholding modelos depend on.

### Phase `W05.P17` - casilla editor

Make the edit session reachable through the capability seam and surface the refusals it currently discards.

- [ ] `W05.P17.S69` - Call the edit session submit path the editor never reaches, through the capability projection seam; `src/cadrumo/entrypoints/tui/modelo/edit/controller.py`.
- [ ] `W05.P17.S70` - Surface the typed stale-baseline refusal the apply operation currently discards; `src/cadrumo/application/modelo/operation_definitions.py`.
- [ ] `W05.P17.S71` - Derive editor writability from the same lock set the calculation engine uses; `src/cadrumo/entrypoints/tui/modelo/edit/fields.py`.
- [ ] `W05.P17.S72` - Disclose override divergence when an operator value displaces a computed one; `src/cadrumo/entrypoints/tui/modelo/edit/review.py`.
- [ ] `W05.P17.S73` - Render each casilla by its declared type and constraints, treating absent constraints as undeclared rather than unconstrained; `src/cadrumo/entrypoints/tui/modelo/edit/fields.py`.

### Phase `W05.P18` - repeated rows

Deliver the row-group editing surface that detail-row modelos have never had.

- [ ] `W05.P18.S74` - Deliver the repeated-row editing surface that detail-row modelos have never had; `src/cadrumo/entrypoints/tui/modelo/edit`.
- [ ] `W05.P18.S75` - Refuse rather than silently truncate when a row group exceeds its declared cardinality; `src/cadrumo/application/modelo/edit_services.py`.

### Phase `W05.P19` - observation entry

Replace command-line JSON with a typed entry surface for the withholding observations that feed calculation bindings.

- [ ] `W05.P19.S76` - Replace command-line aggregation input with a typed observation-entry surface for the withholding modelos; `src/cadrumo/entrypoints/tui/modelo`.
- [ ] `W05.P19.S77` - Confirm the replace-the-set semantics explicitly, because the write is destructive; `src/cadrumo/application/aggregation`.

## Wave `W06` - reconcile and verify

Make comparison attributable and verification complete. Name which comparison ran, render the whole finding rather than a fragment, and disclose withheld advisories instead of omitting them.

### Phase `W06.P20` - attributable reconciliation

Deliver one reconcile destination that names which comparison ran and renders grounded diffs rather than a bare verdict.

- [ ] `W06.P20.S78` - Deliver one reconcile destination whose evidence source is chosen explicitly and named in the result; `src/cadrumo/entrypoints/tui/modelo`.
- [ ] `W06.P20.S79` - Render the grounded diff set as the primary content rather than the binary verdict alone; `src/cadrumo/entrypoints/tui/modelo`.
- [ ] `W06.P20.S80` - Give reconciliation advisories a severity, a resolution action and locale keys in place of authored prose; `src/cadrumo/application/modelo/reconciliation_records.py`.
- [ ] `W06.P20.S81` - Render withheld advisories as explicitly withheld with a count and a reason, never omitted; `src/cadrumo/entrypoints/tui/modelo`.
- [ ] `W06.P20.S82` - Present the cross-modelo consistency check alongside evidence reconciliation but labelled as a different kind of answer; `src/cadrumo/entrypoints/tui/modelo`.
- [ ] `W06.P20.S83` - Resolve or label the reconciliation population that declares known false negatives; `src/cadrumo/application/modelo/_reconcile_population.py`.

### Phase `W06.P21` - complete verification

Render the whole finding under the severity invariant, capture diagnostics at calculation time, and label the gates that cannot fire.

- [ ] `W06.P21.S84` - Render the complete verification finding including message, legal grounding and, for blocking findings, the recovery action the invariant guarantees; `src/cadrumo/entrypoints/tui/modelo/view/verification.py`.
- [ ] `W06.P21.S85` - Capture calculation diagnostics at calculation time into the read model, since the revision does not carry thirty-six of the thirty-eight reasons; `src/cadrumo/application/modelo/calculation_actions.py`.
- [ ] `W06.P21.S86` - State plainly when a verification view was not produced from a calculation in the same session, rather than implying an empty diagnostic set; `src/cadrumo/entrypoints/tui/modelo/view/verification.py`.
- [ ] `W06.P21.S87` - Resolve or label the advisory that cannot fire in production; `src/cadrumo/application/modelo/_m720_redeclaration_gate.py`.

## Wave `W07` - export, import and destinations

Give artefact movement a shared contract in both directions, wire the exporter that already exists, and bring import under the supervisor with the preview and per-item reporting the ledger lane already proved.

### Phase `W07.P22` - destination contract

Introduce the typed destination vocabulary the backend lacks, capability-gated and shared by both adapters.

- [ ] `W07.P22.S88` - Introduce the typed destination contract naming a transport, its artefact family, its capability gate and its availability; `src/cadrumo/application/export`.
- [ ] `W07.P22.S89` - Enumerate the closed destination set once the contract exists, deciding the membership this campaign supports rather than describing the set as closed without listing it; `src/cadrumo/application/export`.
- [ ] `W07.P22.S90` - Enumerate the closed destination set rather than leaving it described as closed; `src/cadrumo/application/export`.

### Phase `W07.P23` - export surfaces

Wire the built workbook exporter, add fichero preview through the existing seam, and stop silent overwrite.

- [ ] `W07.P23.S91` - Wire the offline workbook exporter that is built, styled and has no production caller, releasing it from the unconsumed-export and unused-symbol ratchets that currently name it; `src/cadrumo/application/storage/calc_sheets/workbook_export.py`.
- [ ] `W07.P23.S92` - Expose a fichero preview through the existing payload-consumer arm of the export draft path; `src/cadrumo/application/filing/export.py`.
- [ ] `W07.P23.S93` - Refuse an existing output file rather than silently overwriting it, and reconcile the contradictory path contract; `src/cadrumo/application/filing/export.py`.
- [ ] `W07.P23.S94` - Refuse a revision with no renderable layout, stating the reason, and mark an unverified-completeness export as such on the artefact; `src/cadrumo/application/filing/export.py`.
- [ ] `W07.P23.S95` - Add a bulk export-readiness query so a surface need not build a schema provider per coordinate; `src/cadrumo/application/filing/export.py`.
- [ ] `W07.P23.S152` - Shrink the unconsumed-export and unused-symbol ratchet baselines by the entries the workbook wiring resolves; `dev/quality`.

### Phase `W07.P24` - supervised import

Enrol import as operations and lift the dry-run and per-item outcome contracts from the ledger lane.

- [ ] `W07.P24.S96` - Enrol import as supervised operations, of which none exists today; `src/cadrumo/application/modelo/operation_definitions.py`.
- [ ] `W07.P24.S97` - Lift the dry-run contract from the ledger lane to the modelo side so an import can be previewed before it stages; `src/cadrumo/application/modelo/external_import_actions.py`.
- [ ] `W07.P24.S98` - Lift the per-item typed outcome contract so a partial import reports which items succeeded and which were refused; `src/cadrumo/application/modelo/external_import_actions.py`.
- [ ] `W07.P24.S99` - Report import progress through the operation modal; `src/cadrumo/entrypoints/tui/modelo`.

### Phase `W07.P25` - binding inspector and remote configuration

Deliver the read-only binding inspector and the remote configuration surface under the accepted crossing protocol.

- [ ] `W07.P25.S100` - Deliver the read-only binding inspector from the existing prefill and unsatisfied-binding types; `src/cadrumo/entrypoints/tui/modelo`.
- [ ] `W07.P25.S101` - Refuse binding-definition authoring explicitly and state why when asked; `src/cadrumo/entrypoints/tui/modelo`.
- [ ] `W07.P25.S102` - Deliver the remote configuration surface, delegating interactive authorization under the accepted crossing protocol; `src/cadrumo/entrypoints/tui`.
- [ ] `W07.P25.S103` - Verify a remote folder reference exists rather than accepting a bare identifier unchecked; `src/cadrumo/adapters/outbound/google`.
- [ ] `W07.P25.S104` - Give the orphaned evidence-recapture path a home, since it is the sanctioned way to un-strand a sealed revision; `src/cadrumo/application/modelo/verification_actions.py`.

## Wave `W08` - declaration creation

Discharge the deferred creation mandate on corrected terms, governing the period-first affordance the calendar already offers rather than adding a second one.

### Phase `W08.P26` - period-first creation

Deliver creation as an enrolled operation with its own result receipt, governing the affordance the calendar already offers.

- [ ] `W08.P26.S105` - Offer creation period-first, answering which declarations the period implies for this taxpayer from profile and registry schedules; `src/cadrumo/entrypoints/tui/modelo`.
- [ ] `W08.P26.S106` - Compute absent-work admission before anything is offered, so no offered choice is refused when taken; `src/cadrumo/application/modelo/work_lifecycle.py`.
- [ ] `W08.P26.S107` - Enrol creation as an operation with an atomic work-unit and creation-event write set; `src/cadrumo/application/modelo/operation_definitions.py`.
- [ ] `W08.P26.S108` - Declare creation's own result receipt under the live edit-contract pattern, persisted through the encrypted boundary; `src/cadrumo/application/modelo/edit_contract.py`.
- [ ] `W08.P26.S109` - Present the law-selected revision without offering a choice, and mark an unresolvable or ambiguous revision unavailable with the resolver's reason; `src/cadrumo/entrypoints/tui/modelo`.
- [ ] `W08.P26.S110` - Bring the calendar recovery action under this decision rather than leaving a second ungoverned creation path; `src/cadrumo/entrypoints/tui/declarations/controller.py`.
- [ ] `W08.P26.S111` - Adjudicate each test, allowlist entry and assertion holding creation shut, retiring only those whose invariant the reopening replaces; `src/cadrumo/entrypoints/tui/modelo/tests`.
- [ ] `W08.P26.S150` - Produce the conformance suite the parent decision requires alongside the execution record, since neither alone discharges the interface proof; `src/cadrumo/entrypoints/tui/modelo/tests`.

## Wave `W09` - satellite family dispositions

Deliver, fold, or explicitly close every remaining denominator family, so that no capability is dropped by silence.

### Phase `W09.P27` - first-class satellite surfaces

Deliver the wallet override, the withholding communication lifecycle and the review exchange once its key publication is fixed.

- [ ] `W09.P27.S112` - Deliver the wallet balance and a reachable override from within the workspace whose gate blocks; `src/cadrumo/entrypoints/tui/modelo`.
- [ ] `W09.P27.S113` - Deliver the withholding communication lifecycle surface and the listing verb it lacks; `src/cadrumo/application/modelo`.
- [ ] `W09.P27.S114` - Publish a recipient encryption key so the review exchange can be completed, before any surface presents it; `src/cadrumo/application/modelo`.
- [ ] `W09.P27.S115` - Deliver a review-package catalogue so the exchange does not depend on operator-supplied paths; `src/cadrumo/application/modelo`.
- [ ] `W09.P27.S116` - Deliver the guided review-exchange sequence once its key publication and catalogue exist; `src/cadrumo/entrypoints/tui/modelo`.
- [ ] `W09.P27.S154` - Deliver the wallet seed and correct paths alongside the override, since the family has four rows and surfacing one does not dispose of the others; `src/cadrumo/entrypoints/tui/modelo`.

### Phase `W09.P28` - folded capabilities

Fold the census logbook and the registry-inspection reads into the surfaces that already own their subjects.

- [ ] `W09.P28.S117` - Fold the census logbook into a history panel on the taxpayer profile; `src/cadrumo/entrypoints/tui/profile`.
- [ ] `W09.P28.S118` - Fold the describe, casillas, casilla and formulas reads into the existing schema facet; `src/cadrumo/application/modelo/workspace_models.py`.
- [ ] `W09.P28.S119` - Fold requires and readiness into the overview readiness panel; `src/cadrumo/entrypoints/tui/modelo/view/overview.py`.
- [ ] `W09.P28.S120` - Fold the modelo listing into the work-unit picker; `src/cadrumo/entrypoints/tui/modelo/view/work_select.py`.
- [ ] `W09.P28.S155` - Deliver the census alta, modificacion and baja writes with the alta-first and baja-terminal sequence guard, which is the family's defining behaviour; `src/cadrumo/entrypoints/tui/profile`.
- [ ] `W09.P28.S156` - Fix the census certificate parser that refuses unconditionally, or declare the panel unavailable with that reason rather than shipping a surface that cannot be populated; `src/cadrumo/adapters/inbound/censo/parser.py`.

### Phase `W09.P29` - recorded closures

Record the command-line-only and deferred dispositions with their reopening conditions.

- [ ] `W09.P29.S121` - Record the spreadsheet family and the support matrix as command-line only, with the reason on each row; `dev/quality/modelo_workspace_action_denominator.py`.
- [ ] `W09.P29.S122` - Record projection and comparison as deferred pending a chartered planning surface; `dev/quality/modelo_workspace_action_denominator.py`.
- [ ] `W09.P29.S123` - Record the audit family as deferred until the first production caller of the evidence-bundle service lands; `dev/quality/modelo_workspace_action_denominator.py`.

## Wave `W10` - acceptance and independent review

Prove the campaign against the matrix the governing decision requires, publish final coverage, and submit the workbench to independent review.

### Phase `W10.P30` - acceptance matrix

Prove every delivered surface across four locales, two themes and three geometries with synthetic data.

- [ ] `W10.P30.S124` - Prove every delivered surface across four locales, two themes and three geometries with synthetic sentinel data, treating an omitted cell as a failure; `dev/tui/tests`.
- [ ] `W10.P30.S125` - Publish final denominator coverage with no unadjudicated row remaining; `dev/quality`.
- [ ] `W10.P30.S126` - Prove no delivered surface presents a local mark as authority acceptance, and that no live-write path exists; `src/cadrumo/entrypoints/tui`.

### Phase `W10.P31` - independent review

Submit the completed workbench to independent architecture, accessibility, security and scope review, and publish final coverage.

- [ ] `W10.P31.S127` - Submit the completed workbench to independent architecture, user-experience, accessibility, security and scope review; `.vault/audit`.

## Parallelization

W01 must complete before any annotation or admission claim elsewhere. Within it, the three
phases are independent and may run concurrently under separate writers.

W02 leads with the authorization floor, which blocks every later surface; the four phases behind
it are independent by lane and may run concurrently, one writer per lane. W03 depends on W02
only for the value-handling prerequisites in its first phase; its generator work is otherwise
independent and may run alongside W02. W04 depends on W02 for authorization and on W03 for
anything that renders a projection, but its navigation phase depends on neither and is the
earliest visible progress available.

W05 through W09 depend on W04 for reachability and on W03 for projection, and are largely
independent of each other; the wallet and observation-entry phases should be scheduled early
within that band because they unblock modelo 303 and four withholding modelos respectively.
W10 depends on everything.

Single-writer ownership is mandatory, not advisory. Seven worktrees are live against this
repository and the head moved five times during a single research session. The denominator
module is additionally claimed by an open row in another campaign and must be coordinated
before either touches it.

## Verification

Each wave is verified against the gates its own subject owns, not against a generic checklist.

W01 closes when no inherited hold remains unadjudicated, no row asserts a retired mechanism, and
the denominator reds on a disposition that contradicts the observed shape. That last condition is
the campaign's admission criterion and does not exist today.

W02 closes when no modelo command handler instantiates a repository or declares policy, both
adapters call one service for work review, and a full-screen session can be authorized without a
verb path. Detector tests must fail if policy moves back into an adapter.

W03 closes when coverage is published rather than implied: declared against undeclared revisions,
placed against unplaced casillas, with every unplaced casilla carrying a reason. An undeclared
revision must resolve to an inspection-only projection that says so.

W04 closes when every built destination is reachable by an operator and every modelo mutation
enters through the supervisor.

W05 through W09 close when their surfaces are reachable, their refusals are rendered rather than
discarded, and their denominator rows carry a delivered disposition the gate accepts.

W10 closes when the acceptance matrix passes in full - four locales, two themes, three
geometries, with an omitted cell counted as a failure - no denominator row is unadjudicated, and
independent review has reported.

Two claims in the governing decisions are recorded as unproven and must be measured during
execution rather than assumed: the ordering fidelity figure for the projection, and the
casilla-to-official-description join rate. Byte-level export correctness cannot be proven by
fixture until a golden corpus exists, and no surface may claim it until then.
