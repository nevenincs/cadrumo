---
tags:
  - '#plan'
  - '#ledger-tui-doors'
date: '2026-10-22'
tier: L2
related:
  - '[[2026-09-02-unreachable-capability-tui-navigation-join-adr]]'
modified: '2026-10-22'
body_schema: body-v2
body_hash: 'sha256:b0efed9a0d1d279f1db1bcd49e44e4b8ed3eb83c8071adcc754f2b5d4857d2e0'
---

# `ledger-tui-doors` plan

Give every registered ledger operation its own screen in the TUI Records workspace.

## Description

Approved 2026-10-22. The user approved the base brief, the Records tools seam, the shared-worktree coordination model and the five-domain split in conversation ("lgtm"), after asking that every ledger operation become operable, listable, editable, exportable, importable and categorizable in the TUI through a swarm of per-domain agents.

Of the 87 registered `ledger.*` operations, 17 already have a wired Records screen. The remaining 70 are reachable only through the generic Ctrl+P Operations form, and `ledger.link` has a product door that production never wires. This plan gives each of the 70 its own screen through an injected door that submits the unchanged registered operation for the exact admitted profile and session.

Decision coverage: the navigation-join ADR governs the whole plan. It makes Records a principal workspace whose overview, entries, review, import, classification, evidence and reconciliation areas compose existing application owners without frontend business behaviour. The tools seam in P01 is a frontend-internal composition inside those areas and adds no new area, route or application contract, so it needs no new ADR. Application request and result contracts, the registry and the operation contract manifest are out of scope; an operation that cannot be driven as registered is reported, not worked around.

Every domain agent works from the verified base brief, which carries the architecture, calls interface, design primitives, core modules, file ownership and gates B1 to B8, plus a domain brief that names that domain's operations, request and result models and acceptance scenarios. Domain membership: P02.S02 entries and export, P02.S03 categorisation, P02.S04 evidence and attachments, P02.S05 invoices and reconciliation, P02.S06 registers.

## Steps

### Phase `P01` - build the Records tools seam

The orchestrator adds the tools seam every domain attaches its screens to, before any domain agent starts.

- [x] `P01.S01` - add LedgerToolV1, the injection tools slot, per-area tool tables and the runtime tools composer; `src/cadrumo/entrypoints/tui/ledger/tools.py and src/cadrumo_runtime/host/frontend/tui/runtime_ledger_tools.py`.

### Phase `P02` - open every unwired ledger operation from the TUI

Five domain agents run in parallel, each giving its ledger operations their own Records screens through injected doors.

- [ ] `P02.S02` - give entries and export (16 operations) a paged entry browser, add, lifecycle, health, reset and export tools, and the exclusion submitter; `src/cadrumo/entrypoints/tui/ledger/entries_*.py and runtime_ledger_entries.py`.
- [ ] `P02.S03` - give categorisation (18 operations) bulk and IVA classification, rules, counterparties, splits, allocation, participation and ratios screens; `src/cadrumo/entrypoints/tui/ledger/categorisation_*.py and runtime_ledger_categorisation.py`.
- [ ] `P02.S04` - give evidence and attachments (12 operations) attach, detach, batch intake and evidence view, update, remove and review screens; `src/cadrumo/entrypoints/tui/ledger/evidence_files_*.py and runtime_ledger_evidence_files.py`.
- [ ] `P02.S05` - give records, invoices and reconciliation (9 operations) the record doors, invoice import, wizard and removal, and the link submitter; `src/cadrumo/entrypoints/tui/ledger/invoices_*.py and runtime_ledger_invoices.py`.
- [ ] `P02.S06` - give registers (15 operations) prorrata, bienes de inversion and inventory screens; `src/cadrumo/entrypoints/tui/ledger/registers_*.py and runtime_ledger_registers.py`.

### Phase `P03` - integrate, verify and review

The orchestrator applies locales, registers visual surfaces, runs every gate and reviews the integrated Records workspace.

- [ ] `P03.S07` - apply the domain locale manifests and register the domain harness surfaces; `src/cadrumo/locales and dev/tui/harness/surfaces.py`.
- [ ] `P03.S08` - run gates B1 to B8 over the integrated workspace and review it against the base brief; `src/cadrumo/entrypoints/tui/ledger and src/cadrumo_runtime/host/frontend/tui`.

## Parallelization

P01 runs first and alone; the orchestrator commits it before any domain agent starts. The five P02 Steps then run in parallel, one Opus agent each, in the shared `feature/tui` worktree. Write ownership is disjoint: each agent creates only files named for its domain and their tests. The only shared edit an agent makes is one import and one call in `src/cadrumo_runtime/host/frontend/tui/runtime_ledger_tools.py`, added last and re-read immediately before editing. Agents do not edit `workspace_injection.py`, `routes.py`, `runtime_workbench.py`, `dev/tui/harness/surfaces.py`, the locale catalogues or any application module, and they do not commit. The orchestrator reviews and commits each domain as it lands, so P02 Steps close independently. P03 starts once every P02 Step is closed: the orchestrator applies locale manifests one at a time, registers harness surfaces, then runs the integrated gates and review.

## Verification

- Every one of the 70 operations named in P02 is submitted from its own Records screen through a door wired in `runtime_workbench.py` via the tools composer, proved by its screen test and its runtime door test.
- Gates B1 to B8 from the base brief pass on the integrated tree: no door on the event loop, geometry clean at 80x24, 100x30, 120x40 and 200x50 in both themes, one-page lists with the 30,000-transaction CPU gate, receipt correlation per door, behaviour tests per operation, zero new ruff, import-contract and type diagnostics, and no `just check-locales` finding on the new keys.
- `just test-tui` and the runtime TUI tests under `src/cadrumo_runtime/host/tests/frontend/tui` pass in full.
- A regenerated operation reach map shows no `ledger.*` operation reachable only through Ctrl+P.
- The final integrated review passes against this plan and the navigation-join ADR.
