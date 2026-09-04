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
body_hash: 'sha256:60a2f7f1e3b7da6c5fbd1c6f0b23fdfb1fa00ea914ad057264640b8ecff53342'
---

<!-- RETIRED: S27, S29, S31, S33, S35, S37, S39, S41, S43, S45, S47, S49, S51, S59, S62, S64, S67, S69, S71, S73, S75, S77, S79, S81, S83 -->

# `clitui-ledger` plan

## Description

Execute the accepted backend-authority and interface-parity decision as one gated campaign. `2026-09-04-clitui-ledger-adr` governs the G0 through G4 closure rules, `2026-09-04-clitui-ledger-research` grounds the ownership and product risks, and `2026-09-04-clitui-ledger-reference` is the continuously regenerated capability ledger. Every implementation Step updates the affected matrix rows with code and behavioral evidence before it closes. A newly discovered capability reopens G0 and every later gate whose predicate it affects.

Wave W01 freezes the union denominator, semantic homes, singular plan ownership, and the Ledger TUI implementation hold. Wave W02 recovers every CLI-owned business decision into domain or application authority and cannot start until G0 closes. Wave W03 completes and directly proves the backend product, including artifacts, provenance, model routing, registry routes, and filing compositions, and cannot start until G1 closes. Wave W04 makes the CLI a complete transport adapter only after G2 is accepted. Wave W05 lifts the hold and installs TUI parity only after G3 is accepted. No later Wave may begin for a subset while an earlier gate remains open.

## Steps

## Wave `W01` - freeze the capability denominator and campaign ownership

Close G0 by freezing the executable capability ledger, assigning semantic homes, and recording sole plan ownership plus the Ledger TUI implementation hold before authority migration begins.

### Phase `W01.P01` - define the authoritative capability ledger

Create the stable generated matrix contract, validation, and reference publication used throughout every gate.

- [ ] `W01.P01.S01` - Define stable capability identities, axes, gap classes, applicability, evidence coordinates, and gate predicates; `dev/quality/clitui_ledger_capability_matrix.py`.
- [ ] `W01.P01.S02` - Test identifier stability, denominator completeness, legal state transitions, evidence validation, and closed-gate reopening; `dev/quality/tests/test_clitui_ledger_capability_matrix.py`.
- [ ] `W01.P01.S03` - Generate the continuously updated matrix and gate summary as the authoritative campaign reference; `.vault/reference/2026-09-04-clitui-ledger-reference.md`.

### Phase `W01.P02` - freeze the union denominator and ownership

Enumerate commands, backend-only operations, missing products, registry consumers, artifacts, and installed surfaces with explicit applicability and semantic ownership.

- [ ] `W01.P02.S04` - Enumerate every invocable Ledger command endpoint, sub-operation, handler, schema, and adapter ownership annotation; `src/cadrumo/entrypoints/cli/_app_ledger_command_specs.py`.
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

Close G1 by moving CLI-owned query, mutation, provider, and adjacent-register policy into typed domain or application owners while retaining detector tests that forbid adapter reimplementation.

### Phase `W02.P05` - backport query and composite-read policy

Move scalable query semantics and cross-repository read composition behind frontend-neutral typed use cases.

- [ ] `W02.P05.S15` - Implement typed list, filter, sort, group, stable-page, search, review-state, and rejection query semantics; `src/cadrumo/application/ledger/query_service.py`.
- [ ] `W02.P05.S16` - Implement canonical check, status, history, view, track, staleness, and participation composite reads; `src/cadrumo/application/ledger/composite_reader.py`.
- [ ] `W02.P05.S17` - Implement typed evidence-review, extraction-eligibility, consent-survey, and advisory projections; `src/cadrumo/application/ledger/review_queries.py`.
- [ ] `W02.P05.S18` - Prove stable ordering, missing-last comparisons, paging snapshots, joins, redaction, and refusal outcomes directly; `src/cadrumo/application/ledger/tests/test_query_and_composite_use_cases.py`.

### Phase `W02.P06` - backport core mutation policy

Move manual creation, allocation, classification, and rule-preview decisions from handlers into canonical backend commands.

- [ ] `W02.P06.S19` - Implement operator-intent creation with category, Censo percentage, jurisdiction, FX, prorrata, version, and idempotency policy; `src/cadrumo/application/ledger/operator_commands.py`.
- [ ] `W02.P06.S20` - Implement dedicated allocation and discriminated direct and M210 classification commands; `src/cadrumo/application/ledger/operator_commands.py`.
- [ ] `W02.P06.S21` - Implement canonical rule dry-run through the same eligibility and first-match engine used by live apply; `src/cadrumo/application/ledger/actions_classification.py`.
- [ ] `W02.P06.S22` - Prove creation, allocation, classification, and dry-run success, refusal, replay, stale-baseline, and event behavior; `src/cadrumo/application/ledger/tests/test_operator_commands.py`.

### Phase `W02.P07` - backport provider and review workflows

Move folder import, Drive evidence, consent, review, and model-routing orchestration behind application ports.

- [ ] `W02.P07.S23` - Implement directory and multi-source import planning, dry-run summaries, stable input order, and best-effort results; `src/cadrumo/application/ledger/import_workflows.py`.
- [ ] `W02.P07.S24` - Implement one-item and batch Drive evidence ingestion over provider and secure-custody ports; `src/cadrumo/application/ledger/provider_evidence_workflows.py`.
- [ ] `W02.P07.S25` - Implement extraction consent, eligibility, review filtering, proposal disposition, and atomic selected-apply use cases; `src/cadrumo/application/ledger/review_workflows.py`.
- [ ] `W02.P07.S26` - Implement frontend-neutral classify, saturate, split, preview, and apply routing with typed terminal outcomes; `src/cadrumo/application/ledger/llm_workflows.py`.
- [ ] `W02.P07.S28` - Prove provider faults, cleanup, consent refusal, per-item outcomes, review conflicts, and atomic selected application; `src/cadrumo/application/ledger/tests/test_provider_and_review_workflows.py`.

### Phase `W02.P08` - backport invoice and adjacent-register workflows

Move invoice, counterparty, ratio, prorrata, and bienes operator intent into atomic typed backend use cases.

- [ ] `W02.P08.S30` - Implement invoice add, import, list, mapping, lifecycle advisory, and transaction-link orchestration; `src/cadrumo/application/ledger/invoice_workflows.py`.
- [ ] `W02.P08.S32` - Return typed counterparty-confirmation outcomes from canonical preconditions and persistence; `src/cadrumo/application/ledger/counterparty_establishment.py`.
- [ ] `W02.P08.S34` - Implement atomic usage-ratio workflows with Censo joins, warnings, versions, events, and persistence; `src/cadrumo/application/ledger/ratio_workflows.py`.
- [ ] `W02.P08.S36` - Implement end-to-end prorrata operator commands with legality, precedence, blockers, persistence, and typed results; `src/cadrumo/application/ledger/prorrata_workflows.py`.
- [ ] `W02.P08.S38` - Implement bienes de inversion acquisition and disposal commands from operator intent; `src/cadrumo/application/ledger/investment_goods_workflows.py`.
- [ ] `W02.P08.S40` - Prove invoice, counterparty, ratio, prorrata, and investment-goods workflows with real repositories and co-committed events; `src/cadrumo/application/ledger/tests/test_adjacent_operator_workflows.py`.

### Phase `W02.P09` - prove the clean authority boundary

Publish canonical outcomes, add structural and behavioral detector tests, and close all AUTHORITY findings.

- [ ] `W02.P09.S42` - Consolidate canonical immutable Ledger command and result models for every migrated use case; `src/cadrumo/application/ledger/models.py`.
- [ ] `W02.P09.S44` - Define provider, query, secure-evidence, registry, and repository ports required by the migrated workflows; `src/cadrumo/application/ledger/protocols.py`.
- [ ] `W02.P09.S46` - Add detector tests that fail on repository access, business branching, joins, retry policy, or persistent-event authorship in Ledger handlers; `src/cadrumo/entrypoints/cli/tests/test_ledger_backend_authority.py`.
- [ ] `W02.P09.S48` - Remove every CLI_OWNED annotation and close every AUTHORITY gap only after direct and detector proof is linked; `.vault/reference/2026-09-04-clitui-ledger-reference.md`.

## Wave `W03` - complete and prove the backend product

Close G2 by implementing every missing Ledger operation, artifact, provenance, registry route, and production-behavior proof before any CLI-completion work begins.

### Phase `W03.P10` - complete mutation and provenance semantics

Add batch change sets, immutable notes, atomic evidence replacement and download, exact field history, and complete currency lineage.

- [ ] `W03.P10.S50` - Implement version-bound arbitrary field change sets and atomic multi-row patch application; `src/cadrumo/application/ledger/change_sets.py`.
- [ ] `W03.P10.S52` - Implement append-only note events and atomic batch note append; `src/cadrumo/application/ledger/notes.py`.
- [ ] `W03.P10.S53` - Implement evidence-byte download and atomic evidence replacement with immutable revision lineage and finalized-filing guards; `src/cadrumo/application/ledger/evidence_lifecycle.py`.
- [ ] `W03.P10.S54` - Persist exact changed-field, manual-override, source-column normalization, actor, source, time, and baseline provenance; `src/cadrumo/domain/transactions/change_provenance.py`.
- [ ] `W03.P10.S55` - Carry original and normalized currencies, rate, rate source, effective date, and operation identity through Ledger records; `src/cadrumo/domain/transactions/models.py`.
- [ ] `W03.P10.S56` - Prove atomic rollback, replay ordering, stale baselines, sensitive custody, immutable notes, evidence cleanup, and best-effort item isolation; `src/cadrumo/application/ledger/tests/test_change_sets_notes_and_evidence_lifecycle.py`.

### Phase `W03.P11` - deliver interchange review and recovery products

Implement distinct flat interchange, review exchange, optional Google transport, and secure recovery archive contracts.

- [ ] `W03.P11.S57` - Complete deterministic CSV, JSONL, and XLSX interchange manifests and documented-loss round trips; `src/cadrumo/application/ledger/actions_export.py`.
- [ ] `W03.P11.S58` - Implement the transport-neutral review exchange plan, workbook, sidecar, editable-cell declaration, digest, and return import; `src/cadrumo/application/ledger/review_exchange.py`.
- [ ] `W03.P11.S60` - Implement the optional Google review adapter over the canonical Ledger review exchange plan; `src/cadrumo/adapters/outbound/google/ledger_review_exchange.py`.
- [ ] `W03.P11.S61` - Implement authenticated encrypted versioned Ledger recovery export and fresh-store restore; `src/cadrumo/application/ledger/recovery_archive.py`.
- [ ] `W03.P11.S63` - Prove independent-reader interchange, offline-Google parity, tamper refusal, plaintext cleanup, and canonical restore equality; `src/cadrumo/application/ledger/tests/test_export_products.py`.

### Phase `W03.P12` - complete reviewable model-assisted classification

Route extraction and classification through the canonical model registry with consent, schema, evidence, suggestion, and reviewer provenance.

- [ ] `W03.P12.S65` - Define stable Ledger model capability and output-schema identities in the canonical operation registry; `src/cadrumo/application/operations/registry.py`.
- [ ] `W03.P12.S66` - Record provider, model revision, prompt revision, schema, evidence revisions, suggestion, disposition, and applied change set; `src/cadrumo/application/ledger/llm_review_workflow.py`.
- [ ] `W03.P12.S68` - Enforce local-first custody, eligible-deployment consent, fail-closed incompatibility, and no regulated-fact authorship; `src/cadrumo/application/ledger/llm_workflows.py`.
- [ ] `W03.P12.S70` - Prove model selection, unavailable-model refusal, schema mismatch, consent, provenance, and proposal-only behavior; `src/cadrumo/application/ledger/tests/test_llm_registry_workflows.py`.

### Phase `W03.P13` - close registry calculation and filing routes

Prove all seven Ledger binding families, block every unrouted nonzero observation, and carry full registry and FX provenance into filing evidence.

- [ ] `W03.P13.S72` - Classify every declared route unit in all seven Ledger binding families as proven, incomplete, or not applicable; `src/cadrumo/domain/calculations/registry/bindings.py`.
- [ ] `W03.P13.S74` - Replace the M130 c06 application projection with an honest registry-owned route and prove nonzero c02 production calculation; `src/cadrumo/application/modelo/calculation_route.py`.
- [ ] `W03.P13.S76` - Add live nonzero calculate, verify, evidence, and export paths for M131, M151, M309, M322, and M353; `src/cadrumo/application/modelo/tests/test_ledger_binding_family_routes.py`.
- [ ] `W03.P13.S78` - Block verification, export, and filing for every unrouted nonzero OSS and non-OSS observation; `src/cadrumo/application/modelo/verification_actions.py`.
- [ ] `W03.P13.S80` - Carry registry revision, formula provenance, legal authority, observations, FX source, and FX effective date into immutable filing evidence; `src/cadrumo/domain/modelos/ledger_filing_snapshot.py`.
- [ ] `W03.P13.S82` - Prove pull-calculation parity, exclusions, missing-versus-zero behavior, staleness, and finish-line refusal for every route family; `src/cadrumo/application/modelo/tests/test_ledger_registry_closure.py`.

### Phase `W03.P14` - prove production behavior and close G2

Exercise real repositories, faults, concurrency, artifacts, restore equality, and nonzero calculation compositions before declaring backend completeness.

- [ ] `W03.P14.S84` - Exercise success, refusal, idempotency, concurrency, batch, provider-fault, cancellation, and cleanup behavior against real stores; `src/cadrumo/application/ledger/tests/test_product_completeness.py`.
- [ ] `W03.P14.S85` - Exercise a nonzero Ledger calculate-to-verify-to-evidence-to-export composition across registry and filing boundaries; `src/cadrumo/application/modelo/tests/test_e2e_ledger_filing_products.py`.
- [ ] `W03.P14.S86` - Independently open every produced artifact and restore a recovery archive into a fresh empty store; `src/cadrumo/application/ledger/tests/test_artifact_and_restore_acceptance.py`.
- [ ] `W03.P14.S87` - Close G2 only when every applicable backend, composition, artifact, provenance, registry, and proof axis is PROVEN; `.vault/reference/2026-09-04-clitui-ledger-reference.md`.

## Wave `W04` - make the CLI a complete backend adapter

Close G3 by projecting every applicable backend capability through stable command contracts, deleting displaced policy, and proving readable artifacts and refusal behavior at the interface.

### Phase `W04.P15` - refactor core CLI handlers to delegate

Replace core Ledger read and mutation orchestration with projections over the canonical commands and results.

- [ ] `W04.P15.S88` - Refactor manual add, edit, allocate, classify, link, split, and merge handlers into parsing, invocation, confirmation, and projection only; `src/cadrumo/entrypoints/cli/_ledger.py`.
- [ ] `W04.P15.S89` - Refactor list, filter, sort, group, page, search, and review handlers to delegate typed queries; `src/cadrumo/entrypoints/cli/_ledger_list.py`.
- [ ] `W04.P15.S90` - Refactor check, status, history, view, track, preflight, export, and participation handlers to delegate composite reads; `src/cadrumo/entrypoints/cli/_ledger_read_cli.py`.
- [ ] `W04.P15.S91` - Refactor rule dry-run and apply handlers to delegate one canonical classification engine; `src/cadrumo/entrypoints/cli/_ledger_rules_cli.py`.
- [ ] `W04.P15.S92` - Project canonical commands and results through CLI payloads without redeclaring domain facts; `src/cadrumo/entrypoints/cli/_ledger_payloads.py`.

### Phase `W04.P16` - refactor provider and adjacent CLI handlers to delegate

Replace evidence, LLM, invoice, ratio, prorrata, and bienes orchestration with transport-only adapters.

- [ ] `W04.P16.S93` - Refactor evidence CRUD, download, replace, review, consent, extraction, and batch handlers into transport-only adapters; `src/cadrumo/entrypoints/cli/_ledger_evidence_cli.py`.
- [ ] `W04.P16.S94` - Refactor Drive ingestion and lifecycle handlers to delegate provider-backed workflows; `src/cadrumo/entrypoints/cli/ledger_lifecycle_cli.py`.
- [ ] `W04.P16.S95` - Refactor classify, saturate, split, preview, and apply handlers to delegate model-registry workflows; `src/cadrumo/entrypoints/cli/_ledger_llm_cli.py`.
- [ ] `W04.P16.S96` - Refactor invoice intake, mapping, list, lifecycle, advisory, and linking handlers to delegate invoice workflows; `src/cadrumo/entrypoints/cli/_ledger_business_invoice_cli.py`.
- [ ] `W04.P16.S97` - Refactor ratio handlers to delegate atomic usage-ratio workflows; `src/cadrumo/entrypoints/cli/_ledger_ratios_cli.py`.
- [ ] `W04.P16.S98` - Refactor prorrata handlers to delegate typed end-to-end commands; `src/cadrumo/entrypoints/cli/_prorrata_register_cli.py`.
- [ ] `W04.P16.S99` - Refactor bienes de inversion handlers to delegate operator-intent commands; `src/cadrumo/entrypoints/cli/_bienes_inversion_cli.py`.

### Phase `W04.P17` - complete CLI import export and recovery contracts

Expose every backend artifact product with explicit destinations, dry runs, stable envelopes, and independent readability checks.

- [ ] `W04.P17.S100` - Expose flat interchange export and import with declared-loss manifests and independent round-trip checks; `src/cadrumo/entrypoints/cli/_ledger_read_cli.py`.
- [ ] `W04.P17.S101` - Expose review workbook export, dry-run return import, conflict report, and atomic selected apply; `src/cadrumo/entrypoints/cli/_ledger_review_cli.py`.
- [ ] `W04.P17.S102` - Expose optional Google review exchange through the same review plan and typed provider outcomes; `src/cadrumo/entrypoints/cli/_ledger_review_cli.py`.
- [ ] `W04.P17.S103` - Expose secure archive export and fresh-store restore with explicit collision and integrity refusals; `src/cadrumo/entrypoints/cli/ledger_lifecycle_cli.py`.
- [ ] `W04.P17.S104` - Declare command specs, transport loci, result schemas, help, and locale keys for every added Ledger operation; `src/cadrumo/entrypoints/cli/_app_ledger_command_specs.py`.

### Phase `W04.P18` - prove command parity and close G3

Require every CLI-applicable matrix row to delegate and pass success, refusal, artifact, locale, redaction, and exit-code tests.

- [ ] `W04.P18.S105` - Prove the complete live command graph has no dangling handler, schema, help, or capability declaration; `src/cadrumo/entrypoints/cli/tests/test_app_ledger_command_graph.py`.
- [ ] `W04.P18.S106` - Prove CLI success and typed refusal parity against direct backend results for every applicable row; `src/cadrumo/entrypoints/cli/tests/test_ledger_backend_parity.py`.
- [ ] `W04.P18.S107` - Prove CLI artifact destinations produce independently readable interchange, review, Google, and recovery outputs; `src/cadrumo/entrypoints/cli/tests/test_ledger_artifact_products.py`.
- [ ] `W04.P18.S108` - Prove locale, redaction, confirmation, cancellation, envelope, and exit-code behavior without business-policy branching; `src/cadrumo/entrypoints/cli/tests/test_ledger_adapter_contract.py`.
- [ ] `W04.P18.S109` - Close G3 only when every CLI-applicable matrix row is PROVEN and delegates to its canonical owner; `.vault/reference/2026-09-04-clitui-ledger-reference.md`.

## Wave `W05` - install and prove TUI parity

Close G4 by lifting the hold, reusing the recensused Ledger components over canonical application doors, installing all applicable workflows, and proving cross-surface parity and reachability.

### Phase `W05.P19` - lift the hold and re-census reusable TUI components

Confirm G3 closure, adjudicate existing Ledger components against current backend contracts, and only then authorize production TUI edits.

- [ ] `W05.P19.S110` - Verify G3 closure and record the reviewed authorization that lifts the Ledger TUI implementation hold; `.vault/reference/2026-09-04-clitui-ledger-reference.md`.
- [ ] `W05.P19.S111` - Re-census overview, entries, review, import, classification, evidence, and reconciliation components against current application doors; `src/cadrumo/entrypoints/tui/ledger/`.
- [ ] `W05.P19.S112` - Retire or adapt component-only contracts that duplicate policy or no longer match canonical command and result models; `src/cadrumo/entrypoints/tui/ledger/models.py`.
- [ ] `W05.P19.S113` - Record the reconciled disposition of held Ledger rows in the prior TUI plan before implementation resumes; `.vault/plan/2026-08-11-tui-architecture-plan.md`.

### Phase `W05.P20` - build complete Ledger TUI workflows

Implement read, review, mutation, evidence, import, classification, and artifact workflows over the same typed backend use cases.

- [ ] `W05.P20.S114` - Build scalable list, filter, sort, group, page, search, status, history, view, and track interactions; `src/cadrumo/entrypoints/tui/ledger/entries.py`.
- [ ] `W05.P20.S115` - Build review, classification, rule-preview, model-suggestion, manual-override, and atomic batch-edit interactions; `src/cadrumo/entrypoints/tui/ledger/review.py`.
- [ ] `W05.P20.S116` - Build transaction add, delete, edit, allocate, split, merge, note, and invoice-link interactions; `src/cadrumo/entrypoints/tui/ledger/controller.py`.
- [ ] `W05.P20.S117` - Build evidence attach, metadata, view, download, detach, replace, consent, extraction, and proposal-review interactions; `src/cadrumo/entrypoints/tui/ledger/evidence.py`.
- [ ] `W05.P20.S118` - Build file and folder import, source-column mapping, normalization, currency-lineage, dry-run, and item-result interactions; `src/cadrumo/entrypoints/tui/ledger/import_flow.py`.
- [ ] `W05.P20.S119` - Build flat interchange, review exchange, Google exchange, and secure recovery export and restore interactions; `src/cadrumo/entrypoints/tui/ledger/export_flow.py`.
- [ ] `W05.P20.S120` - Build invoice, ratio, counterparty, prorrata, investment-goods, participation, and affected-filing interactions; `src/cadrumo/entrypoints/tui/ledger/reconciliation.py`.

### Phase `W05.P21` - install navigation and operation feedback

Make every applicable workflow reachable from the installed session with selection handoff, confirmation, progress, refusal, and result presentation.

- [ ] `W05.P21.S121` - Carry selected transaction, prepared import, review change set, and artifact plan identities through Ledger navigation; `src/cadrumo/entrypoints/tui/ledger/routes.py`.
- [ ] `W05.P21.S122` - Compose all Ledger destinations and canonical application services into the installed session; `src/cadrumo/entrypoints/tui/launcher.py`.
- [ ] `W05.P21.S123` - Render operation progress, confirmation, cancellation, partial results, refusals, and completion through shared operation feedback; `src/cadrumo/entrypoints/tui/operations/`.
- [ ] `W05.P21.S124` - Add complete localized Ledger labels, provenance fields, help, refusals, and artifact outcomes through the canonical locale workflow; `src/cadrumo/locales/`.

### Phase `W05.P22` - prove cross-surface parity and close G4

Run installed TUI, backend, CLI, registry, artifact, and accessibility gates and regenerate the final authoritative matrix.

- [ ] `W05.P22.S125` - Prove every applicable Ledger workflow is keyboard-reachable from the installed application and returns to coherent state; `src/cadrumo/entrypoints/tui/ledger/tests/test_installed_ledger_parity.py`.
- [ ] `W05.P22.S126` - Prove backend, CLI, and TUI produce equivalent canonical results and refusal classes for the same capability fixtures; `src/cadrumo/entrypoints/tui/ledger/tests/test_cross_surface_parity.py`.
- [ ] `W05.P22.S127` - Prove readable artifact output, currency and provenance visibility, sensitive-data redaction, and accessibility across Ledger screens; `src/cadrumo/entrypoints/tui/ledger/tests/test_ledger_product_acceptance.py`.
- [ ] `W05.P22.S128` - Regenerate the final capability matrix and close G4 only with every applicable axis PROVEN and every TUI row INSTALLED; `.vault/reference/2026-09-04-clitui-ledger-reference.md`.
- [ ] `W05.P22.S129` - Obtain independent final code-review acceptance for architecture, production safety, and campaign matrix closure; `.vault/audit/2026-09-04-clitui-ledger-final-review-audit.md`.

## Parallelization

Waves are strictly sequential in W01, W02, W03, W04, W05 order. The final Step of each Wave is a hard reviewed gate; downstream work remains blocked until its matrix predicate is satisfied.

Within W01, denominator discovery in P02 may partition across CLI, backend, registry, and TUI readers after P01 defines the schema, but P03 and P04 consume one converged census. Within W02, P05 through P08 may use separate worktrees after their command and result contracts are assigned, while P09 integrates outcomes and runs authority detectors. Within W03, mutation/provenance, artifact, model-assisted, and registry-route Phases may run in parallel only where they do not share models or persistence schemas; P14 is the integration barrier. Within W04, handler files may be refactored in parallel after G2, but command-spec, payload, locale, and artifact changes must be reconciled before P18. Within W05, screen modules may be built in parallel after P19 lifts the hold; routing, installed composition, localization, and final parity tests converge in P21 and P22.

The capability matrix is a shared coordination surface, not a deferred documentation task. Each execution owner claims explicit row identities, refreshes only those rows with current proof, and resolves overlapping ownership before merging.

## Verification

- `vaultspec-core vault plan check` reports no structural errors or warnings, and feature-scoped Vaultspec checks pass after every plan update.
- G0 is accepted only when every union-denominator row has a stable identity, applicability on every axis, semantic owner, typed contract, gap classes, current evidence or explicit UNPROVEN state, and singular plan ownership with the TUI hold recorded.
- G1 is accepted only when no AUTHORITY gap or CLI_OWNED annotation remains, migrated policy has direct domain or application proof, and adapter detector tests fail when business policy is reintroduced.
- G2 is accepted only when every applicable backend, composition, artifact, provenance, registry, and proof axis is PROVEN; real-store tests cover success, refusal, replay, concurrency, batch and provider faults, artifact readers, fresh-store restoration, and a nonzero calculate-to-verify-to-evidence-to-export journey.
- G3 is accepted only when all 78 live command endpoints plus newly admitted commands have resolvable handlers and schemas, every CLI-applicable matrix row delegates to its canonical owner, and success, refusal, locale, redaction, exit-code, and independent artifact checks pass.
- G4 is accepted only when every TUI-applicable row is both PROVEN and INSTALLED, every workflow is keyboard-reachable in the installed application, cross-surface fixtures produce equivalent canonical outcomes, sensitive data remains protected, and accessibility checks pass.
- Flat CSV, JSONL, and XLSX outputs reopen in independent readers and round-trip their declared schemas; review workbook and sidecar identity, digest, editable-cell, conflict, and offline-Google parity checks pass; recovery archives authenticate, reject tampering and collisions, and restore canonical equality into a fresh store.
- All seven Ledger binding families have explicit proven, incomplete, or not-applicable route dispositions; every unrouted nonzero OSS and non-OSS observation blocks verify, export, and filing; filing evidence carries registry, formula, legal-authority, observation, and complete FX lineage.
- The final independent code review accepts architecture boundaries, financial and storage safety, production behavior, command and TUI reachability, and the regenerated matrix with no blocking finding.
