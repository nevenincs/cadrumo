---
tags:
  - '#plan'
  - '#clitui-ledger'
date: '2026-09-04'
tier: L3
related:
  - '[[2026-09-04-clitui-ledger-adr]]'
  - '[[2026-09-04-clitui-ledger-research]]'
  - '[[2026-09-04-clitui-ledger-reference]]'
modified: '2026-09-04'
body_schema: body-v2
body_hash: 'sha256:43000d55014296c49dbaef0ce110cfcc9c3048280febd809a1fa116122b7fb1a'
---

<!-- RETIRED: S27, S29, S31, S33, S35, S37, S39, S41, S43, S45, S47, S49, S51, S59, S62, S64, S67, S69, S71, S73, S75, S77, S79, S81, S83 -->

# `clitui-ledger` plan

## Description

Execute the accepted backend-authority and interface-parity decision as one gated campaign. `2026-09-04-clitui-ledger-adr` governs the G0 through G4 closure rules, `2026-09-04-clitui-ledger-research` grounds the ownership and product risks, and `2026-09-04-clitui-ledger-reference` is the continuously regenerated capability ledger. Every implementation Step updates the affected matrix rows with code and behavioral evidence before it closes. A newly discovered capability reopens G0 and every later gate whose predicate it affects.

Wave W01 freezes the union denominator, semantic homes, singular plan ownership, and the Ledger TUI implementation hold. Wave W02 completes each G1 authority transfer as an inseparable sequence: establish the typed backend owner, cut every affected CLI handler over to it, prove backend behavior and thin-adapter delegation, then close the cohort. Wave W03 cannot start until W02 removes every CLI_OWNED annotation and closes G1; it completes and directly proves the backend product, including artifacts, provenance, model routing, registry routes, and filing compositions. Wave W04 starts only after G2 and enrolls capabilities that did not exist before G2 while closing residual CLI transport and projection defects; it does not repeat the authority cutovers completed in W02. Wave W05 lifts the hold and installs TUI parity only after G3 is accepted. No later Wave may begin for a subset while an earlier gate remains open.

## Steps

## Wave `W01` - freeze the capability denominator and campaign ownership

Close G0 by freezing the executable capability ledger, assigning semantic homes, and recording sole plan ownership plus the Ledger TUI implementation hold before authority migration begins.

### Phase `W01.P01` - define the authoritative capability ledger

Create the stable generated matrix contract, validation, and reference publication used throughout every gate.

- [x] `W01.P01.S01` - Define stable capability identities, axes, gap classes, applicability, evidence coordinates, and gate predicates; `dev/quality/clitui_ledger_capability_matrix.py`.
- [x] `W01.P01.S02` - Test identifier stability, denominator completeness, legal state transitions, evidence validation, and closed-gate reopening; `dev/quality/tests/test_clitui_ledger_capability_matrix.py`.
- [x] `W01.P01.S03` - Generate the continuously updated matrix and gate summary as the authoritative campaign reference; `.vault/reference/2026-09-04-clitui-ledger-reference.md`.

### Phase `W01.P02` - freeze the union denominator and ownership

Enumerate commands, backend-only operations, missing products, registry consumers, artifacts, and installed surfaces with explicit applicability and semantic ownership.

- [x] `W01.P02.S04` - Enumerate every invocable Ledger command endpoint, sub-operation, handler, schema, and adapter ownership annotation; `src/cadrumo/entrypoints/cli/_app_ledger_command_specs.py`.
- [ ] `W01.P02.S05` - Enumerate existing application operations, direct behavioral proof, and backend-only Ledger capabilities; `src/cadrumo/application/ledger/`.
- [ ] `W01.P02.S06` - Enumerate the seven binding families, every declared route, calculation consumer, filing consumer, and unresolved proof obligation; `src/cadrumo/domain/calculations/registry/bindings.py`.
- [ ] `W01.P02.S07` - Enumerate existing Ledger component factories separately from installed navigation reachability; `src/cadrumo/entrypoints/tui/ledger/`.
- [ ] `W01.P02.S08` - Adjudicate canonical semantic homes and typed command-result contracts for every denominator row; `.vault/reference/2026-09-04-clitui-ledger-reference.md`.

### Phase `W01.P03` - record sole plan ownership and the TUI hold

Reconcile overlapping Ledger work without changing production TUI code and make the hold visible in campaign state.

- [ ] `W01.P03.S09` - Record clitui-ledger as sole Ledger parity owner and place unresolved Ledger TUI rows under the implementation hold; `.vault/plan/2026-08-11-tui-architecture-plan.md`.
- [ ] `W01.P03.S10` - Publish the active-plan ownership, hold state, and gate dependency chain without duplicating evidence; `.vault/index/clitui-ledger.index.md`.
- [ ] `W01.P03.S11` - Mark every TUI-applicable matrix row held until G3 and retain component-only versus installed distinctions; `.vault/reference/2026-09-04-clitui-ledger-reference.md`.

### Phase `W01.P04` - adjudicate and close G0

Review every denominator row and require evidence or explicit UNPROVEN state before authority work starts.

- [ ] `W01.P04.S12` - Review every row for explicit applicability, semantic owner, proof state, gap class, and next closure action; `.vault/reference/2026-09-04-clitui-ledger-reference.md`.
- [ ] `W01.P04.S13` - Enforce that new capabilities reopen affected gates and that G0 cannot close over an incomplete union denominator; `dev/quality/tests/test_clitui_ledger_capability_matrix.py`.
- [ ] `W01.P04.S14` - Record G0 closure only after an independent engineering review accepts the frozen matrix; `.vault/reference/2026-09-04-clitui-ledger-reference.md`.

## Wave `W02` - recover backend semantic authority

Close G1 cohort by cohort: implement each typed backend owner, immediately cut affected CLI handlers over to delegation, and retain detector tests that forbid adapter reimplementation.

### Phase `W02.P05` - backport and delegate query and composite-read policy

Implement typed read authorities, cut each affected query and read handler over immediately, then prove the cohort before proceeding.

- [ ] `W02.P05.S15` - Implement typed list, filter, sort, group, stable-page, search, review-state, and rejection query semantics; `src/cadrumo/application/ledger/query_service.py`.
- [ ] `W02.P05.S16` - Implement canonical check, status, history, view, track, staleness, and participation composite reads; `src/cadrumo/application/ledger/composite_reader.py`.
- [ ] `W02.P05.S17` - Implement typed evidence-review, extraction-eligibility, consent-survey, and advisory projections; `src/cadrumo/application/ledger/review_queries.py`.
- [ ] `W02.P05.S18` - Delegate list, filter, sort, group, page, search, and review handling to the typed query use case; `src/cadrumo/entrypoints/cli/_ledger_list.py`.
- [ ] `W02.P05.S19` - Delegate check, status, history, view, track, staleness, and participation handling to composite reads; `src/cadrumo/entrypoints/cli/_ledger_read_cli.py`.
- [ ] `W02.P05.S20` - Delegate Ledger review filtering and projection to the typed review query; `src/cadrumo/entrypoints/cli/_ledger_review_cli.py`.
- [ ] `W02.P05.S21` - Delegate evidence review filtering, blockers, and advisories to the typed evidence review query; `src/cadrumo/entrypoints/cli/_ledger_evidence_review_cli.py`.
- [ ] `W02.P05.S22` - Prove backend read behavior plus thin-handler delegation and detector coverage for the complete cohort; `src/cadrumo/application/ledger/tests/test_query_and_composite_use_cases.py`.

### Phase `W02.P06` - backport and delegate core mutation policy

Implement manual creation, allocation, classification, and rule-preview authorities, cut each affected handler over immediately, then prove the cohort.

- [ ] `W02.P06.S23` - Implement operator-intent creation with category, Censo percentage, jurisdiction, FX, prorrata, version, and idempotency policy; `src/cadrumo/application/ledger/operator_commands.py`.
- [ ] `W02.P06.S24` - Implement dedicated allocation and discriminated direct and M210 classification commands; `src/cadrumo/application/ledger/operator_commands.py`.
- [ ] `W02.P06.S25` - Implement canonical rule dry-run through the same eligibility and first-match engine used by live apply; `src/cadrumo/application/ledger/actions_classification.py`.
- [ ] `W02.P06.S26` - Delegate manual transaction creation to the operator-intent creation command; `src/cadrumo/entrypoints/cli/_ledger.py`.
- [ ] `W02.P06.S28` - Delegate allocation and direct classification to their dedicated backend commands; `src/cadrumo/entrypoints/cli/_ledger.py`.
- [ ] `W02.P06.S30` - Delegate M210 classification routing and completeness decisions to its discriminated backend command; `src/cadrumo/entrypoints/cli/_ledger_m210_classify_cli.py`.
- [ ] `W02.P06.S32` - Delegate rule dry-run and apply to the canonical classification engine; `src/cadrumo/entrypoints/cli/_ledger_rules_cli.py`.
- [ ] `W02.P06.S34` - Prove backend mutation behavior plus thin-handler delegation and detector coverage for the complete cohort; `src/cadrumo/application/ledger/tests/test_operator_commands.py`.

### Phase `W02.P07` - backport and delegate provider and review workflows

Implement import, Drive, evidence-review, consent, and model-routing authorities, cut each affected handler over immediately, then prove the cohort.

- [ ] `W02.P07.S36` - Implement directory and multi-source import planning, dry-run summaries, stable input order, and best-effort results; `src/cadrumo/application/ledger/import_workflows.py`.
- [ ] `W02.P07.S38` - Implement one-item and batch Drive evidence ingestion over provider and secure-custody ports; `src/cadrumo/application/ledger/provider_evidence_workflows.py`.
- [ ] `W02.P07.S40` - Implement extraction consent, eligibility, review filtering, proposal disposition, and atomic selected-apply use cases; `src/cadrumo/application/ledger/review_workflows.py`.
- [ ] `W02.P07.S42` - Implement frontend-neutral classify, saturate, split, preview, and apply routing with typed terminal outcomes; `src/cadrumo/application/ledger/llm_workflows.py`.
- [ ] `W02.P07.S44` - Delegate folder enumeration, per-source execution, and result aggregation to the import workflow; `src/cadrumo/entrypoints/cli/_ledger_import_cli.py`.
- [ ] `W02.P07.S46` - Delegate Drive evidence fetch, MIME decisions, custody, linking, and partial-success semantics to the provider workflow; `src/cadrumo/entrypoints/cli/ledger_lifecycle_cli.py`.
- [ ] `W02.P07.S48` - Delegate extraction eligibility and consent-token decisions to the review workflow; `src/cadrumo/entrypoints/cli/_ledger_evidence_cli.py`.
- [ ] `W02.P07.S50` - Delegate consent survey joins and projections to the port-backed application reader; `src/cadrumo/entrypoints/cli/_ledger_evidence_consent_cli.py`.
- [ ] `W02.P07.S52` - Delegate classify, saturate, split, preview, apply, and terminal model outcomes to the model workflow; `src/cadrumo/entrypoints/cli/_ledger_llm_cli.py`.
- [ ] `W02.P07.S53` - Prove backend provider and review behavior plus thin-handler delegation and detector coverage for the complete cohort; `src/cadrumo/application/ledger/tests/test_provider_and_review_workflows.py`.

### Phase `W02.P08` - backport and delegate invoice and adjacent-register workflows

Implement invoice, counterparty, ratio, prorrata, and bienes authorities, cut each affected handler over immediately, then prove the cohort.

- [ ] `W02.P08.S54` - Implement invoice add, import, list, mapping, lifecycle advisory, and transaction-link orchestration; `src/cadrumo/application/ledger/invoice_workflows.py`.
- [ ] `W02.P08.S55` - Return typed counterparty-confirmation outcomes from canonical preconditions and persistence; `src/cadrumo/application/ledger/counterparty_establishment.py`.
- [ ] `W02.P08.S56` - Implement atomic usage-ratio workflows with Censo joins, warnings, versions, events, and persistence; `src/cadrumo/application/ledger/ratio_workflows.py`.
- [ ] `W02.P08.S57` - Implement end-to-end prorrata operator commands with legality, precedence, blockers, persistence, and typed results; `src/cadrumo/application/ledger/prorrata_workflows.py`.
- [ ] `W02.P08.S58` - Implement bienes de inversion acquisition and disposal commands from operator intent; `src/cadrumo/application/ledger/investment_goods_workflows.py`.
- [ ] `W02.P08.S60` - Delegate invoice intake, mapping, list, lifecycle advisory, and linking to invoice workflows; `src/cadrumo/entrypoints/cli/_ledger_business_invoice_cli.py`.
- [ ] `W02.P08.S61` - Delegate counterparty outcome inference and preconditions to the canonical counterparty command; `src/cadrumo/entrypoints/cli/_ledger_counterparty_cli.py`.
- [ ] `W02.P08.S63` - Delegate Censo joins, ratio persistence, warnings, and events to atomic ratio workflows; `src/cadrumo/entrypoints/cli/_ledger_ratios_cli.py`.
- [ ] `W02.P08.S65` - Delegate prorrata legality, precedence, blockers, persistence, and outcomes to end-to-end commands; `src/cadrumo/entrypoints/cli/_prorrata_register_cli.py`.
- [ ] `W02.P08.S66` - Delegate bienes de inversion record construction and disposal coupling to operator-intent commands; `src/cadrumo/entrypoints/cli/_bienes_inversion_cli.py`.
- [ ] `W02.P08.S68` - Prove backend adjacent-workflow behavior plus thin-handler delegation and detector coverage for the complete cohort; `src/cadrumo/application/ledger/tests/test_adjacent_operator_workflows.py`.

### Phase `W02.P09` - prove the clean authority boundary

Publish canonical outcomes, run structural and behavioral detectors, and close G1 only after every handler delegates and every AUTHORITY finding is closed.

- [ ] `W02.P09.S70` - Consolidate canonical immutable Ledger command and result models for every migrated use case; `src/cadrumo/application/ledger/models.py`.
- [ ] `W02.P09.S72` - Define provider, query, secure-evidence, registry, and repository ports required by the migrated workflows; `src/cadrumo/application/ledger/protocols.py`.
- [ ] `W02.P09.S74` - Add detector tests that fail on repository access, business branching, joins, retry policy, or persistent-event authorship in Ledger handlers; `src/cadrumo/entrypoints/cli/tests/test_ledger_backend_authority.py`.
- [ ] `W02.P09.S76` - Remove every CLI_OWNED annotation and close every AUTHORITY gap only after all cohort cutovers and direct proof are linked; `.vault/reference/2026-09-04-clitui-ledger-reference.md`.

## Wave `W03` - complete and prove the backend product

Close G2 by implementing every missing Ledger operation, artifact, provenance, registry route, and production-behavior proof after every G1 authority cutover is complete.

### Phase `W03.P10` - complete mutation and provenance semantics

Add batch change sets, immutable notes, atomic evidence replacement and download, exact field history, and complete currency lineage.

- [ ] `W03.P10.S78` - Implement version-bound arbitrary field change sets and atomic multi-row patch application; `src/cadrumo/application/ledger/change_sets.py`.
- [ ] `W03.P10.S80` - Implement append-only note events and atomic batch note append; `src/cadrumo/application/ledger/notes.py`.
- [ ] `W03.P10.S82` - Implement evidence-byte download and atomic evidence replacement with immutable revision lineage and finalized-filing guards; `src/cadrumo/application/ledger/evidence_lifecycle.py`.
- [ ] `W03.P10.S84` - Persist exact changed-field, manual-override, source-column normalization, actor, source, time, and baseline provenance; `src/cadrumo/domain/transactions/change_provenance.py`.
- [ ] `W03.P10.S85` - Carry original and normalized currencies, rate, rate source, effective date, and operation identity through Ledger records; `src/cadrumo/domain/transactions/models.py`.
- [ ] `W03.P10.S86` - Prove atomic rollback, replay ordering, stale baselines, sensitive custody, immutable notes, and evidence cleanup; `src/cadrumo/application/ledger/tests/test_change_sets_notes_and_evidence_lifecycle.py`.

### Phase `W03.P11` - deliver interchange review and recovery products

Implement distinct flat interchange, review exchange, optional Google transport, and secure recovery archive contracts.

- [ ] `W03.P11.S87` - Complete deterministic CSV, JSONL, and XLSX interchange manifests and documented-loss round trips; `src/cadrumo/application/ledger/actions_export.py`.
- [ ] `W03.P11.S88` - Implement the transport-neutral review exchange plan, workbook, sidecar, editable-cell declaration, digest, and return import; `src/cadrumo/application/ledger/review_exchange.py`.
- [ ] `W03.P11.S89` - Implement the optional Google review adapter over the canonical Ledger review exchange plan; `src/cadrumo/adapters/outbound/google/ledger_review_exchange.py`.
- [ ] `W03.P11.S90` - Implement authenticated encrypted versioned Ledger recovery export and fresh-store restore; `src/cadrumo/application/ledger/recovery_archive.py`.
- [ ] `W03.P11.S91` - Prove independent-reader interchange, offline-Google parity, tamper refusal, plaintext cleanup, and canonical restore equality; `src/cadrumo/application/ledger/tests/test_export_products.py`.

### Phase `W03.P12` - complete reviewable model-assisted classification

Route extraction and classification through the canonical model registry with consent, schema, evidence, suggestion, and reviewer provenance.

- [ ] `W03.P12.S92` - Define stable Ledger model capability and output-schema identities in the canonical operation registry; `src/cadrumo/application/operations/registry.py`.
- [ ] `W03.P12.S93` - Record provider, model revision, prompt revision, schema, evidence revisions, suggestion, disposition, and applied change set; `src/cadrumo/application/ledger/llm_review_workflow.py`.
- [ ] `W03.P12.S94` - Enforce local-first custody, eligible-deployment consent, fail-closed incompatibility, and no regulated-fact authorship; `src/cadrumo/application/ledger/llm_workflows.py`.
- [ ] `W03.P12.S95` - Prove model selection, unavailable-model refusal, schema mismatch, consent, provenance, and proposal-only behavior; `src/cadrumo/application/ledger/tests/test_llm_registry_workflows.py`.

### Phase `W03.P13` - close registry calculation and filing routes

Prove all seven Ledger binding families, block every unrouted nonzero observation, and carry full registry and FX provenance into filing evidence.

- [ ] `W03.P13.S96` - Classify every declared route unit in all seven Ledger binding families as proven, incomplete, or not applicable; `src/cadrumo/domain/calculations/registry/bindings.py`.
- [ ] `W03.P13.S97` - Replace the M130 c06 application projection with an honest registry-owned route and prove nonzero c02 production calculation; `src/cadrumo/application/modelo/calculation_route.py`.
- [ ] `W03.P13.S98` - Add live nonzero calculate, verify, evidence, and export paths for M131, M151, M309, M322, and M353; `src/cadrumo/application/modelo/tests/test_ledger_binding_family_routes.py`.
- [ ] `W03.P13.S99` - Block verification, export, and filing for every unrouted nonzero OSS and non-OSS observation; `src/cadrumo/application/modelo/verification_actions.py`.
- [ ] `W03.P13.S100` - Carry registry revision, formula provenance, legal authority, observations, FX source, and FX effective date into immutable filing evidence; `src/cadrumo/domain/modelos/ledger_filing_snapshot.py`.
- [ ] `W03.P13.S101` - Prove pull-calculation parity, exclusions, missing-versus-zero behavior, staleness, and finish-line refusal for every route family; `src/cadrumo/application/modelo/tests/test_ledger_registry_closure.py`.

### Phase `W03.P14` - prove production behavior and close G2

Exercise real repositories, faults, concurrency, artifacts, restore equality, and nonzero calculation compositions before declaring backend completeness.

- [ ] `W03.P14.S102` - Exercise success, refusal, idempotency, concurrency, batch, provider-fault, cancellation, and cleanup behavior against real stores; `src/cadrumo/application/ledger/tests/test_product_completeness.py`.
- [ ] `W03.P14.S103` - Exercise a nonzero Ledger calculate-to-verify-to-evidence-to-export composition across registry and filing boundaries; `src/cadrumo/application/modelo/tests/test_e2e_ledger_filing_products.py`.
- [ ] `W03.P14.S104` - Independently open every produced artifact and restore a recovery archive into a fresh empty store; `src/cadrumo/application/ledger/tests/test_artifact_and_restore_acceptance.py`.
- [ ] `W03.P14.S105` - Close G2 only when every applicable backend, composition, artifact, provenance, registry, and proof axis is PROVEN; `.vault/reference/2026-09-04-clitui-ledger-reference.md`.

## Wave `W04` - complete CLI product parity

Close G3 by enrolling capabilities created during G2, removing residual transport and projection defects, and proving complete command and artifact parity without repeating G1 authority cutovers.

### Phase `W04.P15` - enroll G2 core capabilities in the CLI

Add command and payload exposure for batch edits, notes, evidence lifecycle, provenance, and normalization without relocating business policy back into handlers.

- [ ] `W04.P15.S106` - Enroll atomic batch field editing and append-only note commands without duplicating backend mutation policy; `src/cadrumo/entrypoints/cli/_app_ledger_management_command_specs.py`.
- [ ] `W04.P15.S107` - Enroll evidence download and atomic replacement commands with explicit transport loci and result schemas; `src/cadrumo/entrypoints/cli/_app_ledger_evidence_command_specs.py`.
- [ ] `W04.P15.S108` - Expose batch patch and note operations as parsing, confirmation, invocation, and rendering only; `src/cadrumo/entrypoints/cli/_ledger.py`.
- [ ] `W04.P15.S109` - Expose evidence download and replacement as safe destination handling over canonical results; `src/cadrumo/entrypoints/cli/_ledger_evidence_cli.py`.
- [ ] `W04.P15.S110` - Project canonical change-set, note, evidence-revision, manual-override, and currency-provenance results without redeclaring facts; `src/cadrumo/entrypoints/cli/_ledger_payloads.py`.

### Phase `W04.P16` - close residual CLI provider and projection defects

Expose model, registry, provider, and calculation outcomes created by G2 and remove remaining transport-only parity defects.

- [ ] `W04.P16.S111` - Expose model registry, prompt, schema, evidence-revision, suggestion, and reviewer-disposition provenance; `src/cadrumo/entrypoints/cli/_ledger_llm_payloads.py`.
- [ ] `W04.P16.S112` - Expose registry route, calculation consumer, filing consumer, staleness, and unresolved-observation outcomes; `src/cadrumo/entrypoints/cli/_participation_cli.py`.
- [ ] `W04.P16.S113` - Expose source-column mapping, normalization results, FX source, and FX effective-date outcomes for imports; `src/cadrumo/entrypoints/cli/_ledger_import_cli.py`.
- [ ] `W04.P16.S114` - Normalize provider refusal, cancellation, cleanup, and ADR-authorized bulk-ingestion per-item reporting at the CLI boundary; `src/cadrumo/entrypoints/cli/ledger_lifecycle_cli.py`.

### Phase `W04.P17` - complete CLI import export and recovery contracts

Expose every G2 artifact product with explicit destinations, dry runs, stable envelopes, and independent readability checks.

- [ ] `W04.P17.S115` - Expose flat interchange export and import with declared-loss manifests and independent round-trip checks; `src/cadrumo/entrypoints/cli/_ledger_read_cli.py`.
- [ ] `W04.P17.S116` - Expose review workbook export, dry-run return import, conflict report, and atomic selected apply; `src/cadrumo/entrypoints/cli/_ledger_review_cli.py`.
- [ ] `W04.P17.S117` - Expose optional Google review exchange through the same review plan and typed provider outcomes; `src/cadrumo/entrypoints/cli/_ledger_review_cli.py`.
- [ ] `W04.P17.S118` - Expose secure archive export and fresh-store restore with explicit collision and integrity refusals; `src/cadrumo/entrypoints/cli/ledger_lifecycle_cli.py`.
- [ ] `W04.P17.S119` - Declare command specs, transport loci, result schemas, help, and locale keys for every G2-added Ledger operation; `src/cadrumo/entrypoints/cli/_app_ledger_command_specs.py`.

### Phase `W04.P18` - prove command parity and close G3

Require every CLI-applicable matrix row to pass success, refusal, artifact, locale, redaction, exit-code, and delegation detectors.

- [ ] `W04.P18.S120` - Prove the complete live command graph has no dangling handler, schema, help, or capability declaration; `src/cadrumo/entrypoints/cli/tests/test_app_ledger_command_graph.py`.
- [ ] `W04.P18.S121` - Prove CLI success and typed refusal parity against direct backend results for every applicable row; `src/cadrumo/entrypoints/cli/tests/test_ledger_backend_parity.py`.
- [ ] `W04.P18.S122` - Prove CLI artifact destinations produce independently readable interchange, review, Google, and recovery outputs; `src/cadrumo/entrypoints/cli/tests/test_ledger_artifact_products.py`.
- [ ] `W04.P18.S123` - Prove locale, redaction, confirmation, cancellation, envelope, and exit-code behavior without business-policy branching; `src/cadrumo/entrypoints/cli/tests/test_ledger_adapter_contract.py`.
- [ ] `W04.P18.S124` - Close G3 only when every CLI-applicable matrix row is PROVEN, all G2-added capabilities are enrolled, and delegation detectors remain green; `.vault/reference/2026-09-04-clitui-ledger-reference.md`.

## Wave `W05` - install and prove TUI parity

Close G4 by lifting the hold, reusing the recensused Ledger components over canonical application doors, installing all applicable workflows, and proving cross-surface parity and reachability.

### Phase `W05.P19` - lift the hold and re-census reusable TUI components

Confirm G3 closure, adjudicate existing Ledger components against current backend contracts, and only then authorize production TUI edits.

- [ ] `W05.P19.S125` - Verify G3 closure and record the reviewed authorization that lifts the Ledger TUI implementation hold; `.vault/reference/2026-09-04-clitui-ledger-reference.md`.
- [ ] `W05.P19.S126` - Re-census overview, entries, review, import, classification, evidence, and reconciliation components against current application doors; `src/cadrumo/entrypoints/tui/ledger/`.
- [ ] `W05.P19.S127` - Retire or adapt component-only contracts that duplicate policy or no longer match canonical command and result models; `src/cadrumo/entrypoints/tui/ledger/models.py`.
- [ ] `W05.P19.S128` - Record the reconciled disposition of held Ledger rows in the prior TUI plan before implementation resumes; `.vault/plan/2026-08-11-tui-architecture-plan.md`.

### Phase `W05.P20` - build complete Ledger TUI workflows

Implement read, review, mutation, evidence, import, classification, and artifact workflows over the same typed backend use cases.

- [ ] `W05.P20.S129` - Build scalable list, filter, sort, group, page, search, status, history, view, and track interactions; `src/cadrumo/entrypoints/tui/ledger/entries.py`.
- [ ] `W05.P20.S130` - Build review, classification, rule-preview, model-suggestion, manual-override, and atomic batch-edit interactions; `src/cadrumo/entrypoints/tui/ledger/review.py`.
- [ ] `W05.P20.S131` - Build transaction add, delete, edit, allocate, split, merge, note, and invoice-link interactions; `src/cadrumo/entrypoints/tui/ledger/controller.py`.
- [ ] `W05.P20.S132` - Build evidence attach, metadata, view, download, detach, replace, consent, extraction, and proposal-review interactions; `src/cadrumo/entrypoints/tui/ledger/evidence.py`.
- [ ] `W05.P20.S133` - Build file and folder import, source-column mapping, normalization, currency-lineage, dry-run, and item-result interactions; `src/cadrumo/entrypoints/tui/ledger/import_flow.py`.
- [ ] `W05.P20.S134` - Build flat interchange, review exchange, Google exchange, and secure recovery export and restore interactions; `src/cadrumo/entrypoints/tui/ledger/export_flow.py`.
- [ ] `W05.P20.S135` - Build invoice, ratio, counterparty, prorrata, investment-goods, participation, and affected-filing interactions; `src/cadrumo/entrypoints/tui/ledger/reconciliation.py`.

### Phase `W05.P21` - install navigation and operation feedback

Make every applicable workflow reachable from the installed session with selection handoff, confirmation, progress, refusal, and result presentation.

- [ ] `W05.P21.S136` - Carry selected transaction, prepared import, review change set, and artifact plan identities through Ledger navigation; `src/cadrumo/entrypoints/tui/ledger/routes.py`.
- [ ] `W05.P21.S137` - Compose all Ledger destinations and canonical application services into the installed session; `src/cadrumo/entrypoints/tui/launcher.py`.
- [ ] `W05.P21.S138` - Render operation progress, confirmation, cancellation, partial results, refusals, and completion through shared operation feedback; `src/cadrumo/entrypoints/tui/operations/`.
- [ ] `W05.P21.S139` - Add complete localized Ledger labels, provenance fields, help, refusals, and artifact outcomes through the canonical locale workflow; `src/cadrumo/locales/`.

### Phase `W05.P22` - prove cross-surface parity and close G4

Run installed TUI, backend, CLI, registry, artifact, and accessibility gates and regenerate the final authoritative matrix.

- [ ] `W05.P22.S140` - Prove every applicable Ledger workflow is keyboard-reachable from the installed application and returns to coherent state; `src/cadrumo/entrypoints/tui/ledger/tests/test_installed_ledger_parity.py`.
- [ ] `W05.P22.S141` - Prove backend, CLI, and TUI produce equivalent canonical results and refusal classes for the same capability fixtures; `src/cadrumo/entrypoints/tui/ledger/tests/test_cross_surface_parity.py`.
- [ ] `W05.P22.S142` - Prove readable artifact output, currency and provenance visibility, sensitive-data redaction, and accessibility across Ledger screens; `src/cadrumo/entrypoints/tui/ledger/tests/test_ledger_product_acceptance.py`.
- [ ] `W05.P22.S143` - Regenerate the final capability matrix and close G4 only with every applicable axis PROVEN and every TUI row INSTALLED; `.vault/reference/2026-09-04-clitui-ledger-reference.md`.
- [ ] `W05.P22.S144` - Obtain independent final code-review acceptance for architecture, production safety, and campaign matrix closure; `.vault/audit/2026-09-04-clitui-ledger-final-review-audit.md`.

## Parallelization

Waves are strictly sequential in W01, W02, W03, W04, W05 order. The final Step of each Wave is a hard reviewed gate; downstream work remains blocked until its matrix predicate is satisfied.

Within W01, denominator discovery in P02 may partition across CLI, backend, registry, and TUI readers after P01 defines the schema, but P03 and P04 consume one converged census. Within W02, P05 through P08 may use separate worktrees where their backend and handler files do not overlap, but each handler-delegation Step waits for its named backend command or query, and each cohort proof waits for all of its backend and handler Steps. P09 is the G1 integration barrier and must prove all cohort cutovers before W03 starts. Within W03, mutation/provenance, artifact, model-assisted, and registry-route Phases may run in parallel only where they do not share models or persistence schemas; P14 is the G2 integration barrier. Within W04, G2-added command enrollment and residual projection work may run in parallel when command-spec, payload, and locale ownership is disjoint, but P18 reconciles the complete command graph and reruns the G1 delegation detectors. Within W05, screen modules may be built in parallel after P19 lifts the hold; routing, installed composition, localization, and final parity tests converge in P21 and P22.

The capability matrix is a shared coordination surface, not a deferred documentation task. Each execution owner claims explicit row identities, refreshes only those rows with current proof, and resolves overlapping ownership before merging.

## Verification

- `vaultspec-core vault plan check` reports no structural errors or warnings, and feature-scoped Vaultspec checks pass after every plan update.
- G0 is accepted only when every union-denominator row has a stable identity, applicability on every axis, semantic owner, typed contract, gap classes, current evidence or explicit UNPROVEN state, and singular plan ownership with the TUI hold recorded.
- G1 is accepted only when each W02 cohort proves its backend owner and its separate handler cutovers, no AUTHORITY gap or CLI_OWNED annotation remains, and adapter detector tests fail when repository access, joins, provider policy, mutation decisions, or business branching are reintroduced. No W03 Step may begin before this closure is recorded.
- G2 is accepted only when every applicable backend, composition, artifact, provenance, registry, and proof axis is PROVEN; real-store tests cover success, refusal, replay, concurrency, batch and provider faults, artifact readers, fresh-store restoration, and a nonzero calculate-to-verify-to-evidence-to-export journey.
- G3 is accepted only when all 78 baseline command endpoints plus commands admitted for G2-created capabilities have resolvable handlers and schemas, every CLI-applicable matrix row is PROVEN, residual projection and transport defects are closed, and the G1 authority detectors remain green.
- G4 is accepted only when every TUI-applicable row is both PROVEN and INSTALLED, every workflow is keyboard-reachable in the installed application, cross-surface fixtures produce equivalent canonical outcomes, sensitive data remains protected, and accessibility checks pass.
- Flat CSV, JSONL, and XLSX outputs reopen in independent readers and round-trip their declared schemas; review workbook and sidecar identity, digest, editable-cell, conflict, and offline-Google parity checks pass; recovery archives authenticate, reject tampering and collisions, and restore canonical equality into a fresh store.
- All seven Ledger binding families have explicit proven, incomplete, or not-applicable route dispositions; every unrouted nonzero OSS and non-OSS observation blocks verify, export, and filing; filing evidence carries registry, formula, legal-authority, observation, and complete FX lineage.
- The final independent code review accepts architecture boundaries, financial and storage safety, production behavior, command and TUI reachability, and the regenerated matrix with no blocking finding.
