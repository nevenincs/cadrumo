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
body_hash: 'sha256:7def92828767bb238fdebc0552b829b5e2980daca2e493882b0b7cda8eb4034f'
---

# `clitui-ledger` plan

## Description

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
- [ ] `W02.P05.S27` - Implement typed list, filter, sort, group, stable-page, search, review-state, and rejection query semantics; `src/cadrumo/application/ledger/query_service.py`.
- [ ] `W02.P05.S29` - Implement canonical check, status, history, view, track, staleness, and participation composite reads; `src/cadrumo/application/ledger/composite_reader.py`.
- [ ] `W02.P05.S31` - Implement typed evidence-review, extraction-eligibility, consent-survey, and advisory projections; `src/cadrumo/application/ledger/review_queries.py`.
- [ ] `W02.P05.S33` - Prove stable ordering, missing-last comparisons, paging snapshots, joins, redaction, and refusal outcomes directly; `src/cadrumo/application/ledger/tests/test_query_and_composite_use_cases.py`.

### Phase `W02.P06` - backport core mutation policy

Move manual creation, allocation, classification, and rule-preview decisions from handlers into canonical backend commands.

- [ ] `W02.P06.S19` - Implement operator-intent creation with category, Censo percentage, jurisdiction, FX, prorrata, version, and idempotency policy; `src/cadrumo/application/ledger/operator_commands.py`.
- [ ] `W02.P06.S20` - Implement dedicated allocation and discriminated direct and M210 classification commands; `src/cadrumo/application/ledger/operator_commands.py`.
- [ ] `W02.P06.S21` - Implement canonical rule dry-run through the same eligibility and first-match engine used by live apply; `src/cadrumo/application/ledger/actions_classification.py`.
- [ ] `W02.P06.S22` - Prove creation, allocation, classification, and dry-run success, refusal, replay, stale-baseline, and event behavior; `src/cadrumo/application/ledger/tests/test_operator_commands.py`.
- [ ] `W02.P06.S35` - Implement operator-intent creation with category, Censo percentage, jurisdiction, FX, prorrata, version, and idempotency policy; `src/cadrumo/application/ledger/operator_commands.py`.
- [ ] `W02.P06.S37` - Implement dedicated allocation and discriminated direct and M210 classification commands; `src/cadrumo/application/ledger/operator_commands.py`.
- [ ] `W02.P06.S39` - Implement canonical rule dry-run through the same eligibility and first-match engine used by live apply; `src/cadrumo/application/ledger/actions_classification.py`.
- [ ] `W02.P06.S41` - Prove creation, allocation, classification, and dry-run success, refusal, replay, stale-baseline, and event behavior; `src/cadrumo/application/ledger/tests/test_operator_commands.py`.

### Phase `W02.P07` - backport provider and review workflows

Move folder import, Drive evidence, consent, review, and model-routing orchestration behind application ports.

- [ ] `W02.P07.S23` - Implement directory and multi-source import planning, dry-run summaries, stable input order, and best-effort results; `src/cadrumo/application/ledger/import_workflows.py`.
- [ ] `W02.P07.S24` - Implement one-item and batch Drive evidence ingestion over provider and secure-custody ports; `src/cadrumo/application/ledger/provider_evidence_workflows.py`.
- [ ] `W02.P07.S25` - Implement extraction consent, eligibility, review filtering, proposal disposition, and atomic selected-apply use cases; `src/cadrumo/application/ledger/review_workflows.py`.
- [ ] `W02.P07.S26` - Implement frontend-neutral classify, saturate, split, preview, and apply routing with typed terminal outcomes; `src/cadrumo/application/ledger/llm_workflows.py`.
- [ ] `W02.P07.S28` - Prove provider faults, cleanup, consent refusal, per-item outcomes, review conflicts, and atomic selected application; `src/cadrumo/application/ledger/tests/test_provider_and_review_workflows.py`.
- [ ] `W02.P07.S43` - Implement directory and multi-source import planning, dry-run summaries, stable input order, and best-effort results; `src/cadrumo/application/ledger/import_workflows.py`.
- [ ] `W02.P07.S45` - Implement one-item and batch Drive evidence ingestion over provider and secure-custody ports; `src/cadrumo/application/ledger/provider_evidence_workflows.py`.
- [ ] `W02.P07.S47` - Implement extraction consent, eligibility, review filtering, proposal disposition, and atomic selected-apply use cases; `src/cadrumo/application/ledger/review_workflows.py`.
- [ ] `W02.P07.S49` - Implement frontend-neutral classify, saturate, split, preview, and apply routing with typed terminal outcomes; `src/cadrumo/application/ledger/llm_workflows.py`.
- [ ] `W02.P07.S51` - Prove provider faults, cleanup, consent refusal, per-item outcomes, review conflicts, and atomic selected application; `src/cadrumo/application/ledger/tests/test_provider_and_review_workflows.py`.

### Phase `W02.P08` - backport invoice and adjacent-register workflows

Move invoice, counterparty, ratio, prorrata, and bienes operator intent into atomic typed backend use cases.

- [ ] `W02.P08.S30` - Implement invoice add, import, list, mapping, lifecycle advisory, and transaction-link orchestration; `src/cadrumo/application/ledger/invoice_workflows.py`.
- [ ] `W02.P08.S32` - Return typed counterparty-confirmation outcomes from canonical preconditions and persistence; `src/cadrumo/application/ledger/counterparty_establishment.py`.
- [ ] `W02.P08.S34` - Implement atomic usage-ratio workflows with Censo joins, warnings, versions, events, and persistence; `src/cadrumo/application/ledger/ratio_workflows.py`.
- [ ] `W02.P08.S36` - Implement end-to-end prorrata operator commands with legality, precedence, blockers, persistence, and typed results; `src/cadrumo/application/ledger/prorrata_workflows.py`.
- [ ] `W02.P08.S38` - Implement bienes de inversion acquisition and disposal commands from operator intent; `src/cadrumo/application/ledger/investment_goods_workflows.py`.
- [ ] `W02.P08.S40` - Prove invoice, counterparty, ratio, prorrata, and investment-goods workflows with real repositories and co-committed events; `src/cadrumo/application/ledger/tests/test_adjacent_operator_workflows.py`.
- [ ] `W02.P08.S59` - Implement invoice add, import, list, mapping, lifecycle advisory, and transaction-link orchestration; `src/cadrumo/application/ledger/invoice_workflows.py`.
- [ ] `W02.P08.S62` - Return typed counterparty-confirmation outcomes from canonical preconditions and persistence; `src/cadrumo/application/ledger/counterparty_establishment.py`.

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


### Phase `W03.P13` - close registry calculation and filing routes

Prove all seven Ledger binding families, block every unrouted nonzero observation, and carry full registry and FX provenance into filing evidence.


### Phase `W03.P14` - prove production behavior and close G2

Exercise real repositories, faults, concurrency, artifacts, restore equality, and nonzero calculation compositions before declaring backend completeness.


## Wave `W04` - make the CLI a complete backend adapter

Close G3 by projecting every applicable backend capability through stable command contracts, deleting displaced policy, and proving readable artifacts and refusal behavior at the interface.

### Phase `W04.P15` - refactor core CLI handlers to delegate

Replace core Ledger read and mutation orchestration with projections over the canonical commands and results.


### Phase `W04.P16` - refactor provider and adjacent CLI handlers to delegate

Replace evidence, LLM, invoice, ratio, prorrata, and bienes orchestration with transport-only adapters.


### Phase `W04.P17` - complete CLI import export and recovery contracts

Expose every backend artifact product with explicit destinations, dry runs, stable envelopes, and independent readability checks.


### Phase `W04.P18` - prove command parity and close G3

Require every CLI-applicable matrix row to delegate and pass success, refusal, artifact, locale, redaction, and exit-code tests.


## Wave `W05` - install and prove TUI parity

Close G4 by lifting the hold, reusing the recensused Ledger components over canonical application doors, installing all applicable workflows, and proving cross-surface parity and reachability.

### Phase `W05.P19` - lift the hold and re-census reusable TUI components

Confirm G3 closure, adjudicate existing Ledger components against current backend contracts, and only then authorize production TUI edits.


### Phase `W05.P20` - build complete Ledger TUI workflows

Implement read, review, mutation, evidence, import, classification, and artifact workflows over the same typed backend use cases.


### Phase `W05.P21` - install navigation and operation feedback

Make every applicable workflow reachable from the installed session with selection handoff, confirmation, progress, refusal, and result presentation.


### Phase `W05.P22` - prove cross-surface parity and close G4

Run installed TUI, backend, CLI, registry, artifact, and accessibility gates and regenerate the final authoritative matrix.


## Parallelization

## Verification
