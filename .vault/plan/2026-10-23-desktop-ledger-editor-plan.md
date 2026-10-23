---
tags:
  - '#plan'
  - '#desktop-ledger-editor'
date: '2026-10-23'
tier: L2
related:
  - '[[2026-10-23-desktop-ledger-editor-adr]]'
modified: '2026-10-23'
body_schema: body-v2
body_hash: 'sha256:962e5b7cf372c79b4febe3fc34afd69eb4991fcddcdcc9a4eb36916bea4b1cd4'
---

# `desktop-ledger-editor` plan

## Description

Approved 2026-10-23. Basis: in session CADRUMO-UX-LEDGER the owner asked for a table-based desktop batch editor for movements, invoices and categorisation, at parity with the CLI and TUI ledger. They asked for the interface to be prototyped, adversarially critiqued and improved before implementation, and said the work needs no decision from them.

The work adds a Ledger page to the desktop shell and a host channel for the ledger family's registered operations. The decision is `2026-10-23-desktop-ledger-editor-adr`, grounded in `2026-10-23-desktop-ledger-editor-reference`. That ADR governs P01 (the host channel) and bounds every Step that submits an operation. The design system rules come from `2026-10-05-desktop-design-system-adr` (P02, P03, P04). The shell rules on storage, keys and strings come from `2026-10-04-desktop-shell-adr` (P03, P04). The ledger data contracts (`2026-06-10-ledger-interface-contract-adr`, `2026-06-10-ledger-amount-direction-adr`, `2026-06-10-ledger-input-localization-adr`, `2026-06-10-ledger-filter-period-adr`, `2026-06-30-ledger-add-idempotency-adr`, `2026-07-05-ledger-latency-budget-adr`) bound the P03 editors without new decisions. The interaction design is the reviewed prototype, kept with the session's design notes. No other costly decision is involved. A product batch operation for corrections is out of scope (see the ADR's consequences).

## Steps

### Phase `P01` - Host channel for the ledger family

Give the window a closed, typed way to run the ledger family's registered operations over the held person relay, with file tokens and secret bodies, and a scenario host that answers it from synthetic data.

- [x] `P01.S01` - Add the ledger host module: admitted ledger definition list checked against the contract manifest, submit and settle, review read and digest-bound answer, cancel, and registration in the command list; `native/desktop/src-tauri/src/shell/ledger/`.
- [x] `P01.S02` - Add native file and save dialogs and window drag-drop that issue session-bound file tokens, and the own-account secret raw body; `native/desktop/src-tauri/src/shell/ledger/`.
- [x] `P01.S03` - Add the ledger contract types, the optional ledger Host port and its Tauri wiring; `native/desktop/frontend/src/ipc/contract.ts`.
- [ ] `P01.S04` - Answer the ledger port in the scenario host from an in-memory synthetic ledger with refusal, unknown and review cases; `native/desktop/frontend/src/dev/`.

### Phase `P02` - Grid primitive

Add a virtualised, keyboard-first data grid primitive to the design system that every ledger table builds on.

- [ ] `P02.S05` - Add the data grid primitive: windowed rows, sticky header and columns, resizable columns, cell focus, range and row selection, keyboard model; `native/desktop/frontend/src/components/ui/data-grid.tsx`.
- [ ] `P02.S06` - Add grid tests for keyboard, selection, windowing and accessibility; `native/desktop/frontend/tests/`.

### Phase `P03` - Ledger page

Build the Ledger page and its sections from the reviewed prototype, at parity with the CLI and TUI ledger.

- [ ] `P03.S07` - Add the Ledger page to the shell: layout page, rail item, actions, palette contribution, first-pane wiring and states; `native/desktop/frontend/src/App.tsx`.
- [ ] `P03.S08` - Build the Movements grid with readiness strip, toolbar, filters, sort, grouping, columns and saved views; `native/desktop/frontend/src/components/ledger/`.
- [ ] `P03.S09` - Add staged editing: cell editors, paste and fill, undo and redo, changes tray, review and apply with per-row outcomes; `native/desktop/frontend/src/components/ledger/`.
- [ ] `P03.S10` - Add the movement inspector for one row and for a selection, with classification, documents, invoice link, history, declarations and actions; `native/desktop/frontend/src/components/ledger/`.
- [ ] `P03.S11` - Add the import and export dialogs; `native/desktop/frontend/src/components/ledger/`.
- [ ] `P03.S12` - Add the Invoices section with catalogue grid and invoice editor; `native/desktop/frontend/src/components/ledger/`.
- [ ] `P03.S13` - Add the Documents and Matching sections; `native/desktop/frontend/src/components/ledger/`.
- [ ] `P03.S14` - Add the Rules, Registers and Health sections; `native/desktop/frontend/src/components/ledger/`.

### Phase `P04` - Strings, accessibility and verification

Localise every string, prove accessibility, behaviour and performance, and review the integrated feature.

- [ ] `P04.S15` - Declare and translate every ledger chrome string in four locales; `dev/locales/desktop_chrome.py`.
- [ ] `P04.S16` - Add scenario, accessibility, keyboard, privacy and benchmark tests for the Ledger page; `native/desktop/frontend/tests/scenarios/`.
- [ ] `P04.S17` - Review the integrated feature against this plan and its decision; `.vault/audit/`.

## Parallelization

P01 and P02 can run in parallel: the host channel and the grid primitive share no files. P03.S07 needs P01.S03 and P01.S04 (the port and the scenario answer) and P02.S05. P03.S08 to P03.S14 build on S07. S08 and S09 are sequential, while S10 to S14 can run in parallel once S09 lands, with disjoint files under `src/components/ledger/`. P04.S15 follows the P03 Steps whose strings it declares, and P04.S16 follows P04.S15. Shared shell files (`App.tsx`, `layout.ts`, `host.ts`, `contract.ts`) have one writer at a time. Other sessions edit the frontend concurrently, so re-read these files before each patch.

## Verification

- `npm run check` (tsc, ESLint with the design-system rules, Prettier) passes in `native/desktop/frontend`. `cargo test` passes for the host's ledger module, including the test that checks the admitted list against the contract manifest.
- Scenario tests drive the page through the scenario host and cover: reading a period; filtering, sorting and grouping; multi-selection; staged edits with undo; the review-and-apply outcomes (applied, unchanged, refused, unknown with writes paused); the review digest answer; import preview and apply; export; and the invoice editor's refusals.
- An axe audit of every Ledger section reports no violations in the light and dark schemes. The keyboard walk reaches every action without a pointer and never takes a shell-owned chord.
- A privacy test shows that no ledger value reaches local storage, session storage or the log stream, and that data is dropped on sign-out.
- The benchmark renders 5,000 movements and keeps scrolling and selection within the page's budgets.
- Each CLI and TUI ledger capability in the reference's parity list is reachable from the page.
- The final cohesive review (P04.S17) passes.
