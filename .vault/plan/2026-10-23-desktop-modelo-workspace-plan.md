---
tags:
  - '#plan'
  - '#desktop-modelo-workspace'
date: '2026-10-23'
tier: L2
related:
  - '[[2026-10-23-desktop-modelo-workspace-adr]]'
  - '[[2026-09-30-modelo-editor-workbench-adr]]'
  - '[[2026-08-24-modelo-edit-contract-adr]]'
  - '[[2026-10-23-desktop-ledger-editor-adr]]'
  - '[[2026-10-05-desktop-design-system-adr]]'
modified: '2026-10-24'
body_schema: body-v2
body_hash: 'sha256:60fad0c86e6e49473384ceaac68d10b012b91fb75816e0a0c1b0ac1a43a548d6'
---

# `desktop-modelo-workspace` plan

A designed desktop workspace to list, create, fill, check, export, record and correct declarations, with each modelo's editor generated from the application's form read model.

## Description

Approved 2026-10-23

Authorization basis: the owner's instructions of 2026-10-23 in session CADRUMO-UX-MODELO set the objective "to implement and design the actual workspace for creating, editing, reviewing, viewing modelos", required prototyping and round-by-round improvement before work, asked that the work be broken into small pieces, and stated that no new decision is needed and nothing is to be asked. The prototypes converged in their third review round, with all three reviewers voting to freeze them as the implementation target (`2026-10-23-desktop-modelo-workspace-research`).

Decision coverage: `2026-10-23-desktop-modelo-workspace-adr` governs the boundary (closed `modelo.*` family over the held relay, the relay's financial-operand action, bounded large replies, memory-only data) and is the one new decision; it rules P03 and the host-facing parts of P04. `2026-09-30-modelo-editor-workbench-adr` governs the form read model, the state vocabulary and the editing contract the window renders, and rules P01 and P04. `2026-08-24-modelo-edit-contract-adr` governs staging, intents and stale baselines (P01 preflight step, P04 editing and review). `2026-10-23-desktop-ledger-editor-adr` supplies the shared boundary terms and the shared data grid. `2026-10-05-desktop-design-system-adr` governs every visual element. Live writes to the AEAT are outside every step: export writes a local file and recording the filing is local.

On 2026-10-24 the owner reviewed the prototypes in Storybook and approved all of them ("All prototypes look good and approved"), which releases P04 against the frozen design, and asked that the work fan out to several agents, each an opus subagent at medium effort that uses vaultspec-rag and may call sonnet helpers for bounded coding and haiku helpers for context gathering while remaining the principal coder of its lane. The same day the desktop's person session moved from the Python hold to a Rust relay (`native/application/src/person_operations.rs`, another session's commits `4e256a9e95` and `8821a09cfe`), so the financial-operand action of P03.S13 is carried in both, and that session lifted the person reply bound to the relay's assembled-document bound (`931da66b20`), which carries a large form read in one reply and makes P03.S14 unnecessary.

The interaction design is the frozen round-3 prototype under `native/desktop/frontend/src/dev/prototypes/modelo/` (Storybook `Prototypes/Modelo`); its client-side classification (`isTodo`, `asks`, `confirmable`, `display`, `citation`, the next-step ladder, the origin wording) is scaffolding that each P01 step replaces with an application field.

## Steps

### Phase `P01` - The application exposes what the window would otherwise guess

Move every classification and wording decision the prototype had to make into the form read model and its public projection, so the desktop and the TUI render the same answers and the window classifies nothing.

- [x] `P01.S01` - Add per-field standing and asks-the-filer to the form read model and public projection, folding in recorded state, page applicability and blockers, with a parity test against the TUI rule; `src/cadrumo/application/modelo/work_form_models.py`.
- [x] `P01.S02` - Add confirmable, edit address and held-zero to each form field and its public mirror, with tests over the builder forms for 111, 130, 303, 347 and 390; `src/cadrumo/application/modelo/workbench_projection.py`.
- [x] `P01.S03` - Move origin wording selection (origin by source family, named earlier filing, no earlier filing, AEAT import date, held zero) into an application wording module and switch the TUI to it; `src/cadrumo/application/modelo/work_form_wording.py`.
- [x] `P01.S04` - Carry per-field display text from the value presentation (ratio units, masked IBAN, booleans, dates) for the requested language; `src/cadrumo/application/modelo/value_presentation.py`.
- [x] `P01.S05` - Add a form-level next action on the export, filing and calculation-note gates, halting only on a registry-grade admission refusal, with a state table and a gate-agreement test; `src/cadrumo/application/modelo/work_form_next_step.py`.
- [x] `P01.S06` - Move period words and modelo titles into the application wording module and use them in the form and list projections; `src/cadrumo/application/modelo/work_form_wording.py`.
- [x] `P01.S07` - Add a public declarations list row and register the read modelo.declarations.list, carrying state, group, next step, editability and the AEAT axes, with an exact-profile access test; `src/cadrumo/application/modelo/declarations_list.py`.
- [x] `P01.S08` - Move the sources grouping (family, state, boxes fed, owning surface) from the TUI into an application read; `src/cadrumo/application/modelo/work_form_source_groups.py`.
- [x] `P01.S09` - Name the figures outside the form a failed box waits on, with their owning surface, in the casilla help card, and carry citation text for legal references; `src/cadrumo/application/modelo/casilla_help.py`.
- [x] `P01.S10` - Accept raw typed text in edit preflight and return the parsed value, its normalisations and parse refusals per address; `src/cadrumo/application/modelo/edit_operator_input.py`.
- [x] `P01.S30` - Project the header's attention counts, result view, deadline view with its tone, file view and export-gate reason on the form read model, and switch the TUI header to them; `src/cadrumo/application/modelo/work_form_header.py`.
- [x] `P01.S31` - Carry days remaining with tone, group words, creation targets and the AEAT-side steps the read model decides on the declarations list rows, and the zones' and calendar sources' availability on the list read; `src/cadrumo/application/modelo/declarations_list.py`.
- [x] `P01.S32` - Fold the retained apply prerequisite and the AEAT receipt step into the form's next step; `src/cadrumo/application/modelo/work_form_next_step.py`.
- [x] `P01.S33` - Close the review's lower findings: the TUI reads the stored standing, page applicability words are projected, a design-constant figure shows, the typed-entry apply refusal has its own code, the filed wording keys on the recorded closure, and the gate-agreement test drives the real gates; `src/cadrumo/application/modelo/work_form_models.py`.
- [x] `P01.S34` - Move the TUI's issue lines into the application and project them on the form read model in the form's language, with the verdict line, and switch the TUI to them; `src/cadrumo/application/modelo/work_form_issue_lines.py`.
- [x] `P01.S35` - Add a worded history read for one declaration in the modelo family, newest first, with a closed kind per event, read by the CLI history and the shared event table; the TUI has no per-declaration history view; `src/cadrumo/application/modelo/work_history_read.py`.
- [x] `P01.S36` - Add envelopes for a verified Modelo 130 with blocking and incomplete findings and one recorded as filed, read through the real producer; `native/desktop/frontend/scripts/modelo_fixtures.py`.
- [x] `P01.S37` - Word the typed entry's read-back value and parse refusal in the entry's language, the edit preflight's findings and edit refusals, each repeating-record cell's and context field's value text, and state each box's restore offer and confirm value on the form read model; `src/cadrumo/application/modelo/work_form_wording.py`.
- [x] `P01.S38` - Project a worded amendment context for a recorded declaration, with the filed record, the permitted kinds and motives in words and each box's filed value text and edit hints, and parse the corrected values typed by the filer through the canonical typed-entry path, matching the CLI amend wizard; `src/cadrumo/application/modelo/work_amend_contracts.py`.
- [x] `P01.S39` - Project what typing a value over each box does in words, the export offer with its artefacts, elections and their words, the revision's file format, and the recorded filing's receipt state on the form read model, and switch the TUI to them; `src/cadrumo/application/modelo/work_form_export_offer.py`.
- [x] `P01.S40` - Derive the form's export hold and next step from the filing gate's own predicate so no frontend offers a file the gate refuses, test gate agreement over every note kind and working figure, and remove the unused field_needs_filer route; `src/cadrumo/application/modelo/work_form_next_step.py`.
- [x] `P01.S42` - Read each declaration list row at the authority grade its revision declares, as the form does, so an applicability-graded revision shows its real state rather than unreadable; `src/cadrumo/application/modelo/declaration_summary.py`.
- [ ] `P01.S44` - Project the edit admission refusal's words and whether a box takes a typed value on the form read model, report per staged address what a renewal dropped or changed, and give the export offer per-artefact and record availability from the gate predicates, switching the TUI to each; `src/cadrumo/application/modelo/workbench_projection.py`.

### Phase `P02` - One shared Modelo wording for every frontend

Give the Modelo and declarations wording a neutral home in the canonical locale workflow and make the desktop strings carry it, so no frontend invents a sentence.

- [x] `P02.S11` - Move the workbench and declarations keys to a frontend-neutral namespace through the locale workflow, add the missing list and refusal keys in all four languages, and drop terminal key hints from shared sentences; `dev/locales/`.
- [x] `P02.S12` - Include the shared Modelo wording in the generated desktop strings and fail the build on any key the desktop builds that the catalogue lacks; `native/desktop/scripts/content-build.mjs`.

### Phase `P03` - Runtime and host carry the Modelo family

Implement the boundary recorded in the decision: the held relay's financial-operand action, bounded large replies, and the host's closed Modelo family.

- [ ] `P03.S13` - Add the held relay's financial-operand submit for modelo.edit.preflight and modelo.edit.apply, wiping the body and refusing any other definition, with custody and journal tests; `src/cadrumo_runtime/host/session_hold_operations.py`.
- [x] `P03.S14` - Carry relay replies larger than one line by the relay's assembled-document size rather than bounded parts; closed by 931da66b20, which made a separate part protocol unnecessary; `native/desktop/src-tauri/src/agent/person.rs`.
- [x] `P03.S15` - Add the host's typed reads for the declarations list, a form and a box's help card after the calendar view's pattern; `native/desktop/src-tauri/src/shell/modelo/`.
- [ ] `P03.S16` - Add the host's closed modelo family on the shared settle loop in shell/relay.rs (submit and settle, review by digest, cancel), save and file tokens, and the raw financial-operand body, within the relay's request-size limits, with the closed list checked against the contract manifest; `native/desktop/src-tauri/src/shell/modelo/`.
- [x] `P03.S17` - Add the modelo port to the frontend host, its contract types and scenario answers from envelopes regenerated by a development script; `native/desktop/frontend/src/shell/host.ts`.
- [ ] `P03.S43` - Bound the financial-operand submit and the edit renewal by the relay's assembled-document size in the bridge and the relay, carry numbers and the raw body through the wipe, and prove preflight, renewal and apply on the real Modelo 303 and 390 baselines; `native/desktop/src-tauri/src/agent/person.rs`.
- [ ] `P03.S45` - Generate the stored-subject definitions and the edit body limit from the contract and host facts instead of restating them; `native/desktop/frontend/scripts/modelo_fixtures.py`.

### Phase `P04` - The workspace, built from the frozen prototype

Promote the round-3 prototype into product components on the application's fields, deleting every client-side classification as its application field lands.

- [x] `P04.S18` - Add the declarations page with the new-declaration dialog to the shell (page, action, rail item), on the shared data grid; `native/desktop/frontend/src/components/modelo/DeclarationsPage.tsx`.
- [x] `P04.S19` - Add the workspace shell: header with result and the read model's next action, view tabs with state marks, recorded and refused banners; `native/desktop/frontend/src/components/modelo/Workspace.tsx`.
- [x] `P04.S20` - Render the form from the read model: sections, rows, official grids, repeated records, context facts, binding inputs, unplaced boxes and working figures, one page at a time with section windowing; `native/desktop/frontend/src/components/modelo/form/`.
- [ ] `P04.S21` - Edit boxes in place with the replace-a-source prompt, stage contract intents by edit address, and follow the keyboard model shared with the data grid; `native/desktop/frontend/src/components/modelo/form/ValueCell.tsx`.
- [ ] `P04.S22` - Review and apply through preflight, apply and renew, keeping edits and re-reviewing on a stale baseline and showing an unknown outcome as unknown; `native/desktop/frontend/src/components/modelo/ReviewDialog.tsx`.
- [x] `P04.S23` - Add the details panel on the help card, docked at narrow widths, and the To do rail; `native/desktop/frontend/src/components/modelo/Details.tsx`.
- [x] `P04.S24` - Add the Check view on the form's findings in catalogue wording; `native/desktop/frontend/src/components/modelo/CheckView.tsx`.
- [x] `P04.S25` - Add the Export and record view: the AEAT file through a save token, recording the filing, adding the receipt, and the other copies; `native/desktop/frontend/src/components/modelo/FilingView.tsx`.
- [x] `P04.S26` - Add the Sources view and the History view with correction, rename and discard; `native/desktop/frontend/src/components/modelo/`.
- [x] `P04.S41` - Render the read-only view of a return the AEAT holds from the declarations list, from the same read the TUI's external filing details use, and keep the list's view, sort and search while a declaration is open; `native/desktop/frontend/src/components/modelo/declarations/`.
- [ ] `P04.S46` - Render the new admission, typing, renewal and availability fields, show every correction and creation outcome in catalogue words, and type the presentation tables against the generated enums; `native/desktop/frontend/src/components/modelo/`.

### Phase `P05` - Proof

Prove the workspace in the browser and the packaged window over real envelopes, and review it against this plan and its decisions.

- [ ] `P05.S27` - Add Playwright scenarios over regenerated envelopes: refused 390, held-zero and filled 130, check findings, stale export, recorded with and without receipt, hub AEAT-only and maybe rows, all four languages, missing-key and raw-identifier gates, axe; `native/desktop/frontend/tests/modelo.spec.ts`.
- [ ] `P05.S28` - Check in the packaged window that no declaration data reaches storage, logs or diagnostics and that sign-out discards it; `native/desktop/tests/`.
- [ ] `P05.S29` - Review the integrated work against this plan, the decision and the frozen prototype, and record findings in the feature audit; `.vault/audit/`.
- [ ] `P05.S47` - Add scenario answers from real envelopes for apply, renewal, export, recording, receipt and correction, and specs proving staged edits survive a renewal, an unknown apply holds until a re-read and a recorded filing differs from a verified receipt; `native/desktop/frontend/tests/scenarios/modelo.spec.ts`.

## Parallelization

P01, P02 and the first two P03 steps (relay and reply parts) have no dependencies on each other and can run in parallel; inside P01 the next-action step follows the standing and confirmable steps, and the list-row step follows the period-words step. The P03 host steps follow the relay and reply-part steps, and the frontend port follows the host. Each P04 step follows the P01 field it renders and the P03 port. P05 runs last.

From 2026-10-24 the remaining work runs in lanes, each owned by one principal agent with disjoint write scope; the orchestrator (session CADRUMO-UX-MODELO) integrates, runs shared gates and makes every commit:

- Review lane: the formal P01 phase-close review against the governing decisions, appended to this feature's audit; read-only on code.
- Host lane: P03.S15 then P03.S16, writing only `native/desktop/src-tauri/src/shell/modelo/` and, through the orchestrator, the one-line registrations in the shared shell module and command list.
- Port lane: P03.S17, writing `native/desktop/frontend/src/shell/modelo*.ts`, the modelo part of the scenario host and the envelope regeneration script, with the host command names mirrored from the ledger family; it follows the host lane's command shapes.
- Wording lane: the rest of P02.S11 and P02.S12, writing `dev/locales/` and the catalogues; catalogue writes wait for the desktop ledger work's locale queue, and `dev/locales/desktop_chrome.py` edits are coordinated with that work.
- Component lanes (P04), launched once the port lane's contract types land: one lane per component directory under `native/desktop/frontend/src/components/modelo/` (declarations page; workspace shell and views; generated form view and editing; details, review and filing dialogs).

P05 runs after P04, in the orchestrator's session.

The shell files `App.tsx`, `src/shell/layout.ts`, `src/shell/host.ts`, `src/shell/tauriHost.ts`, `src/ipc/contract.ts`, `src/dev/scenarioHost.ts` and the Tauri command list are also edited by the desktop ledger editor work (session CADRUMO-UX-LEDGER); edits there are coordinated with that session, re-read before every patch and kept minimal. The data grid primitive `src/components/ui/data-grid.tsx` is owned by that work; the declarations page consumes it.

## Verification

- Every P01 field is proven through the real builder over the published registry for 111, 130, 303, 347 and 390, and agrees with the TUI and with the export, filing and calculation-note gates; the public projection round trip holds.
- The relay's financial-operand action delivers an amount to operand custody and never to a journal, log or plain payload, and refuses any other definition and any oversize body.
- The frontend contains no classification of a box, a declaration or a finding: no origin, standing, confirmability, next-step or wording rule outside rendering the application's fields.
- The Playwright scenarios pass in all four languages and both schemes with no missing catalogue key, raw identifier or console error, and axe reports no violations; the same scenarios pass in the packaged window.
- Missing is never drawn as zero, local filing, exported file and AEAT-observed state read distinctly, and nothing is offered that submits to the AEAT.
- The final review against this plan, `2026-10-23-desktop-modelo-workspace-adr` and the frozen prototype passes.
