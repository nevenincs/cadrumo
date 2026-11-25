---
tags:
  - '#plan'
  - '#frontend-polish'
date: '2026-11-02'
tier: L1
related:
  - '[[2026-10-05-desktop-design-system-adr]]'
  - '[[2026-10-04-desktop-shell-adr]]'
  - '[[2026-10-23-desktop-ledger-editor-adr]]'
  - '[[2026-10-13-provider-settings-adr]]'
  - '[[2026-10-25-agent-owned-models-adr]]'
  - '[[2026-06-04-calendar-live-filing-integration-adr]]'
  - '[[2026-06-05-calendar-filing-semantics-adr]]'
  - '[[2026-06-30-obligation-coverage-completeness-adr]]'
  - '[[2026-10-29-desktop-aeat-sync-adr]]'
  - '[[2026-06-19-iva-compensation-override-cli-adr]]'
  - '[[2026-06-10-calculation-aggregation-taxonomy-adr]]'
  - '[[2026-10-23-desktop-modelo-workspace-adr]]'
  - '[[2026-07-12-multilang-externalization-adr]]'
  - '[[2026-06-26-binding-fold-in-carry-unification-adr]]'
modified: '2026-11-03'
body_schema: body-v2
body_hash: 'sha256:e20a95a12aeb85be597ba6679dc3f03121b105d04f5ed44570b14c52157ba66d'
---

# `frontend-polish` plan

## Description

Approved 2026-11-02

The user explicitly authorized continued hardening and polish across the complete React/Tauri frontend, with this session personally implementing changes, Terra agents inspecting and summarizing code/decisions, and Sol 6.1 high designing confirmed capability-visibility gaps. Authorization covers removing redundancy without losing information or functionality, readability, correctness, accessibility and evidence-backed performance improvements.

This is an application-wide coverage commitment, not a claim that the whole frontend has been audited. S01-S07 are the first evidence-backed repair candidates. Confirm production reachability and governing decisions before each edit; correct or retire a disproven candidate rather than manufacture a change. S08-S15 are bounded coverage reviews: each produces the exact inspected workflow inventory, findings and verification evidence in the rolling frontend-polish Audit. Insert separate cohesive repair Steps for newly established findings using the owning plan verbs, and finish those repairs before closing the relevant coverage Step. Sound surfaces may remain unchanged. S16 begins with measurement and inserts bounded implementation Steps only for demonstrated product costs.

Accepted authority: desktop-design-system and desktop-shell govern all presentation and host boundaries; desktop-ledger-editor governs S01, S05, S07 and S10; provider-settings and agent-owned-models govern S03-S04 and S13-S14; desktop-aeat-sync and the linked calendar live/filing/coverage decisions govern S06 and S12. S02 also follows the current workbench-currentness and architecture rules. Review and link additional accepted decisions before implementing findings in remaining surfaces. No new dependency, persistence contract, backend authority or costly architecture change is decided by this plan; an uncovered costly decision follows the ADR workflow before dependent implementation.

Initial evidence is the three Terra surface reviews and Sol design briefs from this session. Distinguish observed code defects from unproven account-transition scenarios. The ledger is keyed by reader in App and remounts on profile change; do not claim that its descendant hooks currently expose another profile through that production path. Declarations allocate new memory on reader changes; the confirmed cache concern is a late same-profile list reply overwriting invalidation after workspace entry. Agent direct non-null reader transition reachability still needs verification.

The completed calendar coverage, calendar/messages identity guards and single-pass log counts precede this plan. Their seven focused browser regressions, TypeScript and scoped lint/format evidence are recorded in the session; they do not count as complete coverage of their surrounding surfaces. The development-only five-row DataTable lookup is deliberately deprioritized because no current product consumer benefits.

WINDOWMANAGER completed docking, tabbed/floating/fullscreen layout, pane-header/control consolidation, App integration and their native window changes through commits ba5bf9b288 and c436e4ddf6. Its temporary header/test/locale reservation is released. Preserve that implementation and reuse its unchanged verification evidence in integration review; coordinate any new overlap before editing.

## Steps

- [x] `S01` - Harden document and register reads against changed payloads, hidden views and late replies; `native/desktop/frontend/src/components/ledger/documents/useLedgerRead.ts, native/desktop/frontend/src/components/ledger/setup/SetupParts.tsx`.
- [x] `S22` - Restore a single main landmark around the dock workspace and verify full-window accessibility; `native/desktop/frontend/src/components/docking/DockWorkspace.tsx, native/desktop/frontend/tests/scenarios/docking.spec.ts, native/desktop/frontend/tests/scenarios/ledger-setup.spec.ts`.
- [x] `S02` - Prevent obsolete declarations-list reads from overwriting shared workspace cache invalidation; `native/desktop/frontend/src/components/modelo/declarations/`.
- [x] `S03` - Retire stale provider mutation results and prevent old reads from replacing newly accepted settings; `native/desktop/frontend/src/shell/providerSettings.ts, native/desktop/frontend/src/shell/agentViews.ts`.
- [x] `S04` - Bind reading-model selections and agent observations to the current reader lifecycle; `native/desktop/frontend/src/shell/readingModel.ts, native/desktop/frontend/src/shell/agentLive.ts, native/desktop/frontend/src/components/AgentColumn.tsx`.
- [x] `S05` - Show every available matching-evidence chip without extra disclosure controls; `native/desktop/frontend/src/components/ledger/matching/MatchQueue.tsx`.
- [x] `S06` - Distinguish failed AEAT result refreshes and unavailable empty outcomes from confirmed empty observations; `native/desktop/frontend/src/components/aeatSync/Results.tsx, native/desktop/frontend/src/shell/aeatSyncResults.ts`.
- [x] `S25` - Require host-requested unknown-outcome acknowledgement for exact AEAT retry scopes and prevent overlapping requests; `native/desktop/frontend/src/components/aeatSync/Results.tsx, native/desktop/frontend/src/dev/aeatSyncResultsFixture.ts, native/desktop/frontend/tests/scenarios/aeat-sync.spec.ts`.
- [x] `S07` - Keep invoice grid row identity stable across unrelated editor and notification updates; `native/desktop/frontend/src/components/ledger/invoices/InvoicesSection.tsx`.
- [x] `S18` - Repair shared suggestion visibility and combobox keyboard escape, and verify grid focus when an active column is hidden; `native/desktop/frontend/src/components/ui/, native/desktop/frontend/tests/scenarios/`.
- [x] `S08` - Complete shared-control and typed-editor review for duplication, keyboard access, focus and narrow layouts; `native/desktop/frontend/src/components/ui/, native/desktop/frontend/src/components/editors/`.
- [x] `S09` - Complete profile, account and authentication workflow review for clear forms, validation and safe transitions; `native/desktop/frontend/src/components/profile/, native/desktop/frontend/src/components/SignIn.tsx, native/desktop/frontend/src/components/AccountMenu.tsx`.
- [x] `S10` - Complete remaining ledger workflow review across movements, invoices, documents, assets, registers and transfers; `native/desktop/frontend/src/components/ledger/`.
- [x] `S19` - Keep declaration creation outcome holds across selection and navigation, and require authoritative completion plus a successful list refresh; `native/desktop/frontend/src/shell/modeloWriteHolds.ts, native/desktop/frontend/src/components/modelo/WriteHoldNotice.tsx, native/desktop/frontend/src/components/modelo/declarations/, native/desktop/frontend/src/dev/modeloFixture.ts, native/desktop/frontend/tests/scenarios/modelo-declarations.spec.ts, native/desktop/frontend/tests/live/modelo-write-holds.unit.ts, dev/locales/desktop_workspace_keys.py, src/cadrumo/locales/`.
- [x] `S20` - Keep modelo writes held across navigation and failed post-write refresh, preserving unknown settlement and list invalidation; `native/desktop/frontend/src/components/modelo/, native/desktop/frontend/src/shell/modeloWriteHolds.ts, native/desktop/frontend/tests/scenarios/modelo*.spec.ts, native/desktop/frontend/tests/live/modelo-write-holds.unit.ts`.
- [x] `S21` - Expose returned reconciliation differences and advisory limitations using the Sol design brief and localized labels; `native/desktop/frontend/src/components/modelo/dialogs/, native/desktop/frontend/src/dev/, dev/locales/, native/desktop/frontend/tests/scenarios/modelo.spec.ts`.
- [x] `S11` - Complete modelo workflow review from declaration selection through editing, review, calculation, export and reconciliation; `native/desktop/frontend/src/components/modelo/, native/desktop/frontend/src/shell/modelo.ts`.
- [x] `S23` - Keep AEAT progress uncertainty visible before the first snapshot and after a failed observation of completed work; `native/desktop/frontend/src/components/aeatSync/, native/desktop/frontend/src/shell/aeatSyncRun.ts, native/desktop/frontend/tests/scenarios/aeat-sync.spec.ts`.
- [x] `S24` - Recover refused Sede dialog answers and viewport updates without replaying uncertain person input; `native/desktop/frontend/src/components/browser/useSedeView.ts, native/desktop/frontend/tests/scenarios/sede-browser.spec.ts, native/desktop/frontend/src/dev/`.
- [x] `S12` - Complete AEAT and browser workflow review including preparation, progress, outcomes, notifications and calendar interactions; `native/desktop/frontend/src/components/aeatSync/, native/desktop/frontend/src/components/browser/, native/desktop/frontend/src/components/calendar/`.
- [x] `S13` - Complete agent conversation, approval, clarification, attachments, documents and skills workflow review; `native/desktop/frontend/src/components/agent/, native/desktop/frontend/src/shell/agentPermission.ts, native/desktop/frontend/src/shell/agentClarification.ts`.
- [x] `S14` - Complete settings, provider, model and provisioning workflow review; `native/desktop/frontend/src/components/settings/, native/desktop/frontend/src/components/setup/, native/desktop/frontend/src/shell/provisioning.ts`.
- [x] `S15` - Complete diagnostics, logs, terminals, documentation, search and command-palette review; `native/desktop/frontend/src/components/RecordList.tsx, native/desktop/frontend/src/components/TerminalPane.tsx, native/desktop/frontend/src/components/DocsFrame.tsx, native/desktop/frontend/src/components/CommandPalette.tsx`.
- [ ] `S16` - Measure cross-surface read, rendering, subscription and retained-state costs and implement justified improvements; `native/desktop/frontend/src/shell/, native/desktop/frontend/scripts/benchmark.mjs, native/desktop/frontend/tests/`.
- [ ] `S17` - Verify integrated workflows and close the complete surface coverage audit; `native/desktop/frontend/tests/, native/desktop/tests/, .vault/audit/`.
- [x] `S26` - Make every sent attachment name and skill path readable by keyboard and touch; `native/desktop/frontend/src/components/agent/Transcript.tsx, native/desktop/frontend/src/components/agent/SkillDialog.tsx, native/desktop/frontend/tests/scenarios/agent*.spec.ts`.
- [x] `S27` - Preserve import and export file tokens across pending picker and export outcomes; `native/desktop/frontend/src/components/ledger/transfer/, native/desktop/frontend/tests/scenarios/ledger-transfer.spec.ts, native/desktop/frontend/tests/scenarios/ledger-pause.spec.ts`.
- [x] `S28` - Bind counterparty decisions to exact lookup identity and expose real confirmation, conflict and unresolved outcomes; `native/desktop/frontend/src/components/ledger/setup/CounterpartiesPane.tsx, native/desktop/frontend/src/shell/ledgerSetup.ts, native/desktop/frontend/src/dev/, native/desktop/frontend/tests/scenarios/ledger-setup.spec.ts, src/cadrumo/application/ledger/entry_limits.py, src/cadrumo/application/ledger/counterparty_operation.py, src/cadrumo/application/ledger/tests/test_entry_limits.py, dev/locales/, src/cadrumo/locales/`.
- [x] `S29` - Distinguish pending and failed Local AI discovery from no lanes and offer model-list read recovery; `native/desktop/frontend/src/shell/localAiLanes.ts, native/desktop/frontend/src/shell/localModels.ts, native/desktop/frontend/src/components/AgentColumn.tsx, native/desktop/frontend/src/components/setup/LocalAi.tsx, native/desktop/frontend/src/components/setup/ProvisioningPanel.tsx, native/desktop/frontend/src/components/settings/LocalModels.tsx, native/desktop/frontend/src/dev/agentFixtureHost.ts, native/desktop/frontend/tests/scenarios/local-models.spec.ts`.
- [x] `S30` - Render palette search results only for their query and distinguish unavailable search; `native/desktop/frontend/src/components/CommandPalette.tsx, native/desktop/frontend/tests/scenarios/palette.spec.ts, dev/locales/`.
- [x] `S31` - Render served context-fact box numbers and regenerate canonical Modelo fixtures to match the current contract; `native/desktop/frontend/src/components/modelo/form/RecordsBlock.tsx, native/desktop/frontend/src/dev/fixtures/modelo/, native/desktop/frontend/src/shell/modeloContract.ts, native/desktop/frontend/tests/scenarios/modelo.spec.ts`.
- [x] `S32` - Restore canonical frontend input generation with accepted diagnostic severity parity and lossless public export-offer projection; `src/cadrumo/application/modelo/calculation_notes.py, src/cadrumo/application/modelo/workbench_projection.py, src/cadrumo/application/modelo/projection_operation.py, src/cadrumo/core/errors/registry/_application_modelo.py, src/cadrumo/application/modelo/tests/, native/desktop/frontend/scripts/modelo_fixtures.py, native/desktop/frontend/src/shell/modeloContract.ts, native/desktop/frontend/src/components/modelo/workspace/CreditsPanel.tsx, native/desktop/frontend/src/components/modelo/workspace/CreditsView.tsx, native/desktop/frontend/src/components/modelo/workspace/EstimateView.tsx`.
- [x] `S33` - Expose the supported local declaration PDF comparison beside receipt import, preserving backend refusals and write holds; `native/desktop/frontend/src/components/modelo/dialogs/FilingView.tsx, native/desktop/frontend/src/dev/modeloFixture.ts, native/desktop/frontend/tests/scenarios/modelo.spec.ts, dev/locales/, src/cadrumo/locales/`.
- [x] `S34` - Retry failed casilla help in place without changing selection or staged edits; `native/desktop/frontend/src/components/modelo/details/, native/desktop/frontend/tests/scenarios/modelo.spec.ts`.
- [x] `S35` - Keep delayed agent clarification and approval results within their originating conversation and request owner; `native/desktop/frontend/src/components/AgentColumn.tsx, native/desktop/frontend/tests/scenarios/agent-prompts.spec.ts`.
- [x] `S36` - Mount one responsive Modelo details panel and preserve its state across narrow and wide layouts; `native/desktop/frontend/src/components/modelo/workspace/Workspace.tsx, native/desktop/frontend/tests/scenarios/modelo.spec.ts`.
- [x] `S37` - Show refused browser input once per view without storing or replaying person input; `native/desktop/frontend/src/components/browser/, native/desktop/frontend/src/dev/sedeViewFixture.ts, native/desktop/frontend/tests/scenarios/sede-browser.spec.ts, dev/locales/, src/cadrumo/locales/`.
- [x] `S38` - Recover failed log subscriptions in place with current-owner isolation; `native/desktop/frontend/src/shell/useHostLogs.ts, native/desktop/frontend/src/components/RecordList.tsx, native/desktop/frontend/src/components/HostRecordList.tsx, native/desktop/frontend/src/dev/, native/desktop/frontend/tests/scenarios/logs.spec.ts, dev/locales/, src/cadrumo/locales/`.
- [x] `S39` - Expose served IVA wallet balances and explicit managed operations with profile-scoped outcome holds; `native/desktop/frontend/src/components/modelo/, native/desktop/frontend/src/shell/modeloWriteHolds.ts, native/desktop/frontend/src/dev/modeloFixture.ts, native/desktop/frontend/scripts/modelo_fixtures.py, native/desktop/frontend/tests/scenarios/modelo*.spec.ts, dev/locales/, src/cadrumo/locales/`.
- [x] `S40` - Show identical filing block explanations once while retaining action-specific refusal and accessible associations; `native/desktop/frontend/src/components/modelo/dialogs/FilingView.tsx, native/desktop/frontend/tests/scenarios/modelo.spec.ts`.
- [x] `S41` - Reduce repeated locale-key payload in bundled chrome while preserving canonical catalogue semantics; `native/desktop/frontend/vite.config.ts, native/desktop/frontend/dev/chrome-catalogue.ts, native/desktop/frontend/tests/live/chrome-catalogue.unit.ts`.
- [x] `S42` - Keep confirmation focus on its delayed matching link only while the person remains at the confirmed result; `native/desktop/frontend/src/components/ledger/documents/DraftReview.tsx, native/desktop/frontend/tests/scenarios/ledger-documents.spec.ts`.
- [x] `S43` - Fit docked ledger minimum widths through split geometry without overwriting the chosen layout; `native/desktop/frontend/src/shell/docking.ts, native/desktop/frontend/src/components/docking/DockWorkspace.tsx, native/desktop/frontend/src/App.tsx, native/desktop/frontend/tests/scenarios/ledger-inspector.spec.ts, native/desktop/frontend/tests/scenarios/docking.spec.ts, native/desktop/frontend/tests/live/docking.unit.ts`.
- [x] `S44` - Restore visible Docs history controls within the single dock header and verify Docs and terminal integration; `native/desktop/frontend/src/App.tsx, native/desktop/frontend/src/components/docking/DockWorkspace.tsx, native/desktop/frontend/tests/scenarios/scenarios.spec.ts, native/desktop/frontend/tests/desktop.spec.ts`.
- [x] `S45` - Repair benchmark setup and timing for the current desktop and record valid measurements without weakening budgets; `native/desktop/frontend/scripts/benchmark.mjs`.

## Parallelization

All product edits are implemented by the parent session, serially. Terra agents may conduct independent read-only discovery for S01-S17; Sol 6.1 high may prepare design briefs for confirmed missing or misleading information. Neither receives implementation ownership. Read-only work may overlap implementation but final review evaluates the resulting stable changes.

Verification has one owner at a time. WINDOWMANAGER explicitly handed build/test ownership back to CADRUMO-FRONTEND after its final expanded-group correction passed; this session now owns checks. Obtain explicit handoff before another session starts checks, and return ownership explicitly when delegating a verification window. Preserve the running canonical dev server for user review. Coordinate shared locale files and declaration registries before writes, and preserve unrelated edits. Vault operations here are scoped to frontend-polish; other workstreams scope their records separately.

## Verification

For each repaired workflow, reproduce its meaningful failure boundary and verify the real owning hook/component: deferred success/failure, request replacement, hiding/unmount, supported account transitions, successful empty versus unavailable/stale, and no duplicate mutation where relevant. Keep local projections, remote acquisition, local export and actual submission distinct.

Use current scenario fixtures and shared primitives; add focused coverage only where it detects a behavioral regression. Check readable narrow layouts, keyboard/focus behavior, translated text in en/es/ca/hu and preservation of existing controls/information. Verify removed elements have an equivalent accessible home. Do not infer packaged authority from simulated browser hosts.

Use npm run check and relevant Playwright scenarios with canonical generated inputs under build/windows-x64, followed by required broader checks at integration boundaries. Native changes use the enrolled CMake targets and real configuration; report missing secrets/configuration separately without fabricating them. Reuse unchanged verification evidence; report existing unrelated failures separately. Performance claims require representative before/after measurements and must name the product path affected.

S08-S15 coverage inventories must account for each owned surface, its success/empty/loading/failure/stale states and the actions it exposes; a file-name map alone is not completion. Review missing backend capability exposure against typed contracts and intentional authority restrictions. The final review reconciles those inventories with the application navigation and host capability map, including WINDOWMANAGER integration, and records any remaining limitations explicitly.

Complete only when every Step and inserted repair Step is closed, required checks are evidenced and the integrated code review passes. Keep checkpoints and the execution ledger through the owning verbs; no completion claim based only on the amount of code changed.
