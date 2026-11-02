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
modified: '2026-11-02'
body_schema: body-v2
body_hash: 'sha256:81b201be226335ab88f6339835037184c56a0e583080138aa35ddd76ac69bafa'
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
- [ ] `S10` - Complete remaining ledger workflow review across movements, invoices, documents, assets, registers and transfers; `native/desktop/frontend/src/components/ledger/`.
- [ ] `S19` - Preserve uncertain declaration creation across chooser changes and require authoritative settlement before another write; `native/desktop/frontend/src/components/modelo/declarations/, native/desktop/frontend/tests/scenarios/modelo-declarations.spec.ts`.
- [ ] `S20` - Keep modelo writes held across navigation and failed post-write refresh, preserving unknown settlement and list invalidation; `native/desktop/frontend/src/components/modelo/workspace/, native/desktop/frontend/src/components/modelo/filing/, native/desktop/frontend/tests/scenarios/modelo*.spec.ts`.
- [ ] `S21` - Expose returned reconciliation differences and advisory limitations using the Sol design brief and localized labels; `native/desktop/frontend/src/components/modelo/filing/, native/desktop/frontend/src/dev/, dev/locales/, native/desktop/frontend/tests/scenarios/modelo.spec.ts`.
- [ ] `S11` - Complete modelo workflow review from declaration selection through editing, review, calculation, export and reconciliation; `native/desktop/frontend/src/components/modelo/, native/desktop/frontend/src/shell/modelo.ts`.
- [ ] `S23` - Keep AEAT progress uncertainty visible before the first snapshot and after a failed observation of completed work; `native/desktop/frontend/src/components/aeatSync/, native/desktop/frontend/src/shell/aeatSyncRun.ts, native/desktop/frontend/tests/scenarios/aeat-sync.spec.ts`.
- [ ] `S24` - Recover refused Sede dialog answers and viewport updates without replaying uncertain person input; `native/desktop/frontend/src/components/browser/useSedeView.ts, native/desktop/frontend/tests/scenarios/sede-browser.spec.ts, native/desktop/frontend/src/dev/`.
- [ ] `S12` - Complete AEAT and browser workflow review including preparation, progress, outcomes, notifications and calendar interactions; `native/desktop/frontend/src/components/aeatSync/, native/desktop/frontend/src/components/browser/, native/desktop/frontend/src/components/calendar/`.
- [ ] `S13` - Complete agent conversation, approval, clarification, attachments, documents and skills workflow review; `native/desktop/frontend/src/components/agent/, native/desktop/frontend/src/shell/agentPermission.ts, native/desktop/frontend/src/shell/agentClarification.ts`.
- [ ] `S14` - Complete settings, provider, model and provisioning workflow review; `native/desktop/frontend/src/components/settings/, native/desktop/frontend/src/components/setup/, native/desktop/frontend/src/shell/provisioning.ts`.
- [ ] `S15` - Complete diagnostics, logs, terminals, documentation, search and command-palette review; `native/desktop/frontend/src/components/RecordList.tsx, native/desktop/frontend/src/components/TerminalPane.tsx, native/desktop/frontend/src/components/DocsFrame.tsx, native/desktop/frontend/src/components/CommandPalette.tsx`.
- [ ] `S16` - Measure cross-surface read, rendering, subscription and retained-state costs and implement justified improvements; `native/desktop/frontend/src/shell/, native/desktop/frontend/scripts/benchmark.mjs, native/desktop/frontend/tests/`.
- [ ] `S17` - Verify integrated workflows and close the complete surface coverage audit; `native/desktop/frontend/tests/, native/desktop/tests/, .vault/audit/`.
- [x] `S26` - Make every sent attachment name and skill path readable by keyboard and touch; `native/desktop/frontend/src/components/agent/Transcript.tsx, native/desktop/frontend/src/components/agent/SkillDialog.tsx, native/desktop/frontend/tests/scenarios/agent*.spec.ts`.
- [ ] `S27` - Preserve import and export file tokens across pending picker and export outcomes; `native/desktop/frontend/src/components/ledger/transfer/, native/desktop/frontend/tests/scenarios/ledger-transfer.spec.ts, native/desktop/frontend/tests/scenarios/ledger-pause.spec.ts`.
- [ ] `S28` - Bind counterparty decisions to the requested identifier and retire obsolete answers; `native/desktop/frontend/src/components/ledger/setup/CounterpartiesPane.tsx, native/desktop/frontend/tests/scenarios/ledger-setup.spec.ts`.

## Parallelization

All product edits are implemented by the parent session, serially. Terra agents may conduct independent read-only discovery for S01-S17; Sol 6.1 high may prepare design briefs for confirmed missing or misleading information. Neither receives implementation ownership. Read-only work may overlap implementation but final review evaluates the resulting stable changes.

Verification has one owner at a time. WINDOWMANAGER explicitly handed build/test ownership back to CADRUMO-FRONTEND after its final expanded-group correction passed; this session now owns checks. Obtain explicit handoff before another session starts checks, and return ownership explicitly when delegating a verification window. Preserve the running canonical dev server for user review. Coordinate shared locale files and declaration registries before writes, and preserve unrelated edits. Vault operations here are scoped to frontend-polish; other workstreams scope their records separately.

## Verification

For each repaired workflow, reproduce its meaningful failure boundary and verify the real owning hook/component: deferred success/failure, request replacement, hiding/unmount, supported account transitions, successful empty versus unavailable/stale, and no duplicate mutation where relevant. Keep local projections, remote acquisition, local export and actual submission distinct.

Use current scenario fixtures and shared primitives; add focused coverage only where it detects a behavioral regression. Check readable narrow layouts, keyboard/focus behavior, translated text in en/es/ca/hu and preservation of existing controls/information. Verify removed elements have an equivalent accessible home. Do not infer packaged authority from simulated browser hosts.

Use npm run check and relevant Playwright scenarios with canonical generated inputs under build/windows-x64, followed by required broader checks at integration boundaries. Native changes use the enrolled CMake targets and real configuration; report missing secrets/configuration separately without fabricating them. Reuse unchanged verification evidence; report existing unrelated failures separately. Performance claims require representative before/after measurements and must name the product path affected.

S08-S15 coverage inventories must account for each owned surface, its success/empty/loading/failure/stale states and the actions it exposes; a file-name map alone is not completion. Review missing backend capability exposure against typed contracts and intentional authority restrictions. The final review reconciles those inventories with the application navigation and host capability map, including WINDOWMANAGER integration, and records any remaining limitations explicitly.

Complete only when every Step and inserted repair Step is closed, required checks are evidenced and the integrated code review passes. Keep checkpoints and the execution ledger through the owning verbs; no completion claim based only on the amount of code changed.
