---
tags:
  - '#plan'
  - '#provisioning-panel'
date: '2026-10-28'
tier: L1
related:
  - '[[2026-10-18-dependency-provisioning-unified-setup-adr]]'
  - '[[2026-10-24-rust-component-provisioning-adr]]'
  - '[[2026-10-25-agent-owned-models-adr]]'
  - '[[2026-10-27-sede-browser-adr]]'
modified: '2026-10-29'
body_schema: body-v2
body_hash: 'sha256:63e55cc62ef877dc6ea47c1d9fbe01c512b26df390dee5ade22310d6bddc40f6'
---

# `provisioning-panel` plan

## Description

Approved 2026-10-28. Basis: the owner's first-hand request of 2026-10-28 in conversation, which gave the rulings recorded in the 2026-10-28 amendment of 2026-10-18-dependency-provisioning-unified-setup-adr and asked for the work to be carried out by agents (Sonnet high for straightforward changes, Opus medium for architecture).

Replace the desktop's single-run setup dialog with one per-element provisioning panel fed by the engine's one state source. Decision coverage: the unified-setup ADR as amended 2026-10-28 governs the panel, Settings, the global signal and blocked features (S03, S04, S02); 2026-10-24-rust-component-provisioning-adr governs engine ownership, the per-item locks and the local AI parts (S01); 2026-10-25-agent-owned-models-adr governs which models appear as local AI sub-elements (S01, S03, S04); 2026-10-27-sede-browser-adr governs the Sede panel (S02). No further decision is needed.

## Steps

- [x] `S01` - Give the desktop setup host one independent run per item, with per-part progress for the local AI program and model, and replace the snapshot's single setup with runs keyed by item in the Rust wire and the TypeScript contract; `native/desktop/src-tauri/src/shell/setup/, native/application/src/provisioning/ where per-part progress needs it, native/desktop/frontend/src/ipc/contract.ts, native/desktop/frontend/src/shell/setup.ts and tests`.
- [x] `S02` - Route a Sede panel refused for a missing browser to the browser's setup verdict, log the refusal locally as a warning, and show the browser's sentence with the button that opens the provisioning panel; `native/desktop/src-tauri/src/shell/sede_view.rs, src/cadrumo/adapters/outbound/aeat/browser/sede_view.py where the verdict is lost, native/desktop/frontend/src/components/browser/ and tests`.
- [x] `S03` - Build the one provisioning panel and the global provisioning store: one row per engine row with its own action, progress and status said once, the local AI as a dropdown holding one local AI component (Ollama program row plus the existing LocalModels list with custom add, per-model download, progress and remove) that the agent settings' Ollama controls also render in place of their own localAiSetup, a close button, used at startup and from every recovery; delete SetupDialog, SetupAdvisory and the hardcoded kind maps; add the rail Settings spinner overlay; `native/desktop/frontend/src/components/setup/, native/desktop/frontend/src/components/settings/LocalModels.tsx, native/desktop/frontend/src/components/AgentColumn.tsx, native/desktop/frontend/src/shell/setup.ts, native/desktop/frontend/src/shell/provisioningRecovery.ts, native/desktop/frontend/src/App.tsx, locale catalogues via dev.locales, stories and scenario tests`.
- [x] `S04` - Reduce Settings to one provisioning section with a status label and a button opening the panel, remove the Local AI button and the browser section, and conform Settings, the panel and the local AI component to their Storybook stories; `native/desktop/frontend/src/components/Settings.tsx, Settings.stories.tsx, native/desktop/frontend/src/components/setup/ stories, native/desktop/frontend/src/components/settings/LocalModels.stories.tsx`.
- [ ] `S05` - Verify on the dev server and scenarios first, then rebuild the desktop from the current tree and confirm startup panel, per-element installs running together, rail spinner, Settings section and the Sede browser-missing offer; `development build targets and the plan ledger, no product files`.

## Parallelization

S01 and S02 run in parallel: S01 owns the desktop setup host, the engine progress events, the setup wire, `ipc/contract.ts` setup types and `shell/setup.ts`; S02 owns the Sede view path and `components/browser/`. S03 starts after S01 lands, since it builds on the per-item wire. S04 follows S03, which owns the panel's element row that S04 reuses. S05 runs last, once no worker or peer build is active in `build/windows-x64`.

Assignments: S01, S02 and S03 Opus medium (architecture and cross-layer); S04 Sonnet high; S05 Opus medium.

## Verification

- A browser setup and a local AI setup run at the same time, each reviewed, cancelled and resumed on its own; Rust tests cover concurrent items and joining one item.
- No React, Rust host or Python surface enumerates items, kinds, sizes or states of its own; the panel renders the snapshot's rows, and an unknown size never shows as zero.
- The local AI shows the program and each listed model as separate sub-elements with separate progress.
- One React component lists and manages provisioning; it opens at startup, from Settings' one section and from every recovery, states each status once and has a close button; closing never stops a run.
- The rail's Settings button shows the spinner overlay while any run is live, driven by the one global store.
- A Sede panel without a browser logs a local warning and offers the browser's setup.
- Frontend lint, type check, unit and scenario tests, the touched Rust and Python tests pass; the dev server is checked before the rebuild, and the rebuilt app is checked from the current tree.
