---
tags:
  - '#plan'
  - '#ledger-tui-doors'
date: '2026-10-22'
tier: L2
related:
  - '[[2026-09-02-unreachable-capability-tui-navigation-join-adr]]'
  - '[[2026-07-05-ledger-latency-budget-adr]]'
  - '[[2026-10-22-ledger-tui-doors-authenticated-stored-reads-adr]]'
  - '[[2026-08-22-secure-storage-performance-hardening-adr]]'
modified: '2026-10-23'
body_schema: body-v2
body_hash: 'sha256:a0d05aead6a030b405e655e7cbc32b1296f4087c874977f4f5fa0839dc8d59d5'
---

# `ledger-tui-doors` plan

Give every registered ledger operation its own screen in the TUI Records workspace.

## Description

Approved 2026-10-22. The user approved the base brief, the Records tools seam, the shared-worktree coordination model and the five-domain split in conversation ("lgtm"), after asking that every ledger operation become operable, listable, editable, exportable, importable and categorizable in the TUI through a swarm of per-domain agents.

Of the 87 registered `ledger.*` operations, 17 already have a wired Records screen. The remaining 70 are reachable only through the generic Ctrl+P Operations form, and `ledger.link` has a product door that production never wires. This plan gives each of the 70 its own screen through an injected door that submits the unchanged registered operation for the exact admitted profile and session.

Decision coverage: the navigation-join ADR governs the whole plan. It makes Records a principal workspace whose overview, entries, review, import, classification, evidence and reconciliation areas compose existing application owners without frontend business behaviour. The tools seam in P01 is a frontend-internal composition inside those areas and adds no new area, route or application contract, so it needs no new ADR. Application request and result contracts, the registry and the operation contract manifest are out of scope; an operation that cannot be driven as registered is reported, not worked around.

Every domain agent works from the verified base brief, which carries the architecture, calls interface, design primitives, core modules, file ownership and gates B1 to B8, plus a domain brief that names that domain's operations, request and result models and acceptance scenarios. Domain membership: P02.S02 entries and export, P02.S03 categorisation, P02.S04 evidence and attachments, P02.S05 records, invoices and reconciliation, P02.S06 registers.

P04 added 2026-10-22 on the user's instruction. The D1 CPU gate measured a period-filtered `ledger.list` page at about 12.6 CPU-seconds for 30,000 transactions, against the 3-second budget, because the list query loads and decodes the whole catalogue before filtering. The user chose to fix it and to dedicate extra agents to optimisation. TUI enrolment of the ledger operations remains the priority; the optimisation exists so those screens load in usable time. The ledger latency budget ADR governs P04: period-first partitioning through the existing plaintext date index, a per-read completeness gate (stale index falls back to a full scan, never a silent drop), full-scan-versus-partition parity tests, no new index columns, and no change to regulated results. The unfiltered full-catalogue listing stays outside that decision; a lever for it needs its own decision before implementation.

P04.S17 and P04.S18 implement the authenticated-stored-reads ADR, accepted on the user's instruction. P04.S19 was added 2026-10-22 when the user answered "Yes, harden": the filing consumers that default an unaccepted registry value instead of refusing it (income concept, Art. 104.tres tag, cash-accounting treatment, counterparty identification state, and the untyped input-classification failure) must refuse at use against the operation's pinned authority, with typed refusals. It changes no registry data or request contract, and any later widening of the authenticated read's skip set remains a separate decision.

P03.S20 to P03.S23 were added 2026-10-23 as in-scope corrections from the integrated review (`2026-10-23-ledger-tui-doors-integrated-review-audit`). Its three high findings require them: blocking session checks on the event loop, writes abandoned by navigation, and ambiguous write outcomes reported as refusals. Its medium finding on bulk classify adds the fourth. P04.S13 is also governed by the secure-storage performance hardening ADR, which is now linked.

## Steps

### Phase `P01` - build the Records tools seam

The orchestrator adds the tools seam every domain attaches its screens to, before any domain agent starts.

- [x] `P01.S01` - add LedgerToolV1, the injection tools slot, per-area tool tables and the runtime tools composer; `src/cadrumo/entrypoints/tui/ledger/tools.py and src/cadrumo_runtime/host/frontend/tui/runtime_ledger_tools.py`.

### Phase `P02` - open every unwired ledger operation from the TUI

Five domain agents run in parallel, each giving its ledger operations their own Records screens through injected doors.

- [x] `P02.S02` - give entries and export (16 operations) a paged entry browser, add, lifecycle, health, reset and export tools, and the exclusion submitter; `src/cadrumo/entrypoints/tui/ledger/entries_*.py and runtime_ledger_entries.py`.
- [x] `P02.S03` - give categorisation (18 operations) bulk and IVA classification, rules, counterparties, splits, allocation, participation and ratios screens; `src/cadrumo/entrypoints/tui/ledger/categorisation_*.py and runtime_ledger_categorisation.py`.
- [x] `P02.S04` - give evidence and attachments (12 operations) attach, detach, batch intake and evidence view, update, remove and review screens; `src/cadrumo/entrypoints/tui/ledger/evidence_files_*.py and runtime_ledger_evidence_files.py`.
- [x] `P02.S05` - give records, invoices and reconciliation (9 operations) the record doors, invoice import, wizard and removal, and the link submitter; `src/cadrumo/entrypoints/tui/ledger/invoices_*.py and runtime_ledger_invoices.py`.
- [x] `P02.S06` - give registers (15 operations) prorrata, bienes de inversion and inventory screens; `src/cadrumo/entrypoints/tui/ledger/registers_*.py and runtime_ledger_registers.py`.

### Phase `P04` - optimise ledger reads at scale

Dedicated agents make the ledger reads behind the Records screens meet the 30,000-transaction budget, running in parallel with the domain agents.

- [x] `P04.S09` - make a period-filtered ledger.list read only the date-index partition, with the completeness gate, parity tests and the D1 CPU gate as acceptance; `src/cadrumo/application/ledger/list_query.py`.
- [x] `P04.S10` - cut the per-row cost of the full transaction catalogue load without changing encryption, binding or results; `src/cadrumo/adapters/persistence/profile/transactions.py`.
- [x] `P04.S11` - measure every ledger read the Records screens call at 30,000 transactions and rank the overruns with their causes; `dev/ci/tests/test_ledger_tui_reads_benchmark.py`.
- [x] `P04.S12` - stop the domain Transaction model repeating raw revalidation and registry vocabulary lookups for every loaded row; `src/cadrumo/domain/transactions/models.py`.
- [x] `P04.S13` - cut the per-row session freshness checks and repeated object-key digests in the secure object batch read; `src/cadrumo/adapters/persistence/storage/sql/secure_objects.py`.
- [x] `P04.S14` - make workbench generation pair invoices with transactions through an index instead of every invoice against every transaction, with identical suggestions; `src/cadrumo/domain/invoices/service.py`.
- [x] `P04.S15` - load the transaction catalogue once per ledger read, read the period partition for status, check and preflight, and read one row by id for view, track, history and participation; `src/cadrumo/application/ledger`.
- [x] `P04.S16` - stop revalidating the whole invoice catalogue and its registry lookups on every invoice read; `src/cadrumo/domain/invoices/models.py`.
- [x] `P04.S17` - decode authenticated current-schema transaction rows without admission re-derivations, remove duplicated validators, and move the transaction model to pydantic-native coercion; `src/cadrumo/domain/transactions/models.py`.
- [x] `P04.S18` - decode an authenticated current-schema invoice catalogue without admission re-derivations and validate only the invoice a view returns; `src/cadrumo/adapters/persistence/profile/invoices.py`.
- [x] `P04.S19` - make the IVA, Renta and Modelo consumers refuse registry values the pinned authority does not accept at use, with typed refusals, and fix the untyped input-classification KeyError; `src/cadrumo/application/aggregation`.

### Phase `P03` - integrate, verify and review

The orchestrator applies locales, registers visual surfaces, runs every gate and reviews the integrated Records workspace.

- [x] `P03.S07` - apply the domain locale manifests and register the domain harness surfaces; `src/cadrumo/locales and dev/tui/harness/surfaces.py`.
- [ ] `P03.S08` - run gates B1 to B8 over the integrated workspace and review it against the base brief; `src/cadrumo/entrypoints/tui/ledger and src/cadrumo_runtime/host/frontend/tui`.
- [ ] `P03.S20` - move every blocking session check in the categorisation review and invoice import runtime doors off the event loop, with thread-recording tests for each door outside run_operation; `src/cadrumo_runtime/host/frontend/tui/runtime_ledger_categorisation.py and runtime_ledger_invoices.py`.
- [x] `P03.S21` - make the Records workspace refuse area and tool changes while its body has a write in flight, tested per write flow; `src/cadrumo/entrypoints/tui/ledger/controller.py`.
- [ ] `P03.S22` - report a submitted write that times out or settles with an unknown or partial effect as a typed outcome-unknown refusal carrying the operation id, shown as unknown on every write screen; `src/cadrumo_runtime/host/frontend/tui/runtime_profile_session.py`.
- [x] `P03.S23` - send every reviewed row of a bulk-classify page and show the operation's applied and skipped counts; `src/cadrumo/entrypoints/tui/ledger/categorisation_bulk.py`.
- [x] `P03.S24` - give ledger.review and ledger.evidence.review.list dedicated Records doors so no ledger operation is reachable only through Ctrl+P, and name the eight remaining ledger locale key families in full; `src/cadrumo/entrypoints/tui/ledger/review.py, evidence.py and runtime_ledger_*.py`.
- [x] `P03.S25` - make every Records body answer an area choice, so entries add, export and reset, the import flow, invoice entry and the categorisation tools no longer show a navigation table that does nothing; `src/cadrumo/entrypoints/tui/ledger/controller.py and the bodies that bypass handle_navigation_selection`.

## Parallelization

P01 runs first and alone; the orchestrator commits it before any domain agent starts. The five P02 Steps then run in parallel, one Opus agent each, in the shared `feature/tui` worktree. Write ownership is disjoint: each agent creates only files named for its domain and their tests. The only shared edit an agent makes is one import and one call in `src/cadrumo_runtime/host/frontend/tui/runtime_ledger_tools.py`, added last and re-read immediately before editing. Agents do not edit `workspace_injection.py`, `routes.py`, `runtime_workbench.py`, `dev/tui/harness/surfaces.py`, the locale catalogues or any application module, and they do not commit. The orchestrator reviews and commits each domain as it lands, so P02 Steps close independently. The three P04 Steps run in parallel with P02 and with each other, one Opus agent each, with disjoint ownership: P04.S09 owns `src/cadrumo/application/ledger/list_query.py` and its tests, P04.S10 owns `src/cadrumo/adapters/persistence/profile/transactions.py` and its tests, and P04.S11 owns only its benchmark module and makes no product change. None of them edits a file another agent owns; a change needed in another owner's file goes to the orchestrator. P03 starts once every P02 and P04 Step is closed: the orchestrator applies locale manifests one at a time, registers harness surfaces, then runs the integrated gates and review.

## Verification

- Every one of the 70 operations named in P02 is submitted from its own Records screen through a door wired in `runtime_workbench.py` via the tools composer, proved by its screen test and its runtime door test.
- Gates B1 to B8 from the base brief pass on the integrated tree: no door on the event loop, geometry clean at 80x24, 100x30, 120x40 and 200x50 in both themes, one-page lists with the 30,000-transaction CPU gate, receipt correlation per door, behaviour tests per operation, zero new ruff, import-contract and type diagnostics, and no `just check-locales` finding on the new keys.
- `just test-tui` and the runtime TUI tests under `src/cadrumo_runtime/host/tests/frontend/tui` pass in full.
- A regenerated operation reach map shows no `ledger.*` operation reachable only through Ctrl+P.
- The final integrated review passes against this plan and the navigation-join ADR.
