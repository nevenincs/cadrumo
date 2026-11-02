---
tags:
  - '#plan'
  - '#cadrumo-windowmanager'
date: '2026-11-02'
tier: L1
related:
  - '[[2026-10-04-desktop-shell-adr]]'
  - '[[2026-10-05-desktop-design-system-adr]]'
  - '[[2026-10-09-desktop-titlebar-adr]]'
modified: '2026-11-02'
body_schema: body-v2
body_hash: 'sha256:c76903f8db0b4f76a79d902779a1abb4d7ca97d1268a880cf6a9713dfbb955cc'
---

# `cadrumo-windowmanager` plan

## Description

Approved 2026-11-02. The user requested implementation of dockable, tabbed panels with directional splits, swapping, expansion, true fullscreen, floating and single-instance enforcement. Preserve CADRUMO-FRONTEND's five owned files. The desktop-shell and desktop-titlebar amendments govern presentation persistence, retained mounted content, and main-window fullscreen operations. The design-system ADR governs primitives, tokens and localization. Floating panes remain inside the main window, as communicated while awaiting the optional clarification about native secondary windows.

## Steps

- [x] `S01` - Implement validated single-instance docking layout state and migration; `native/desktop/frontend/src/shell/docking.ts (new), shell/layout.ts and focused layout tests`.
- [x] `S02` - Integrate docking presentation with a single tab strip owning pane titles and layout controls; `native/desktop/frontend/src/App.tsx, components/docking, PaneHeader.tsx, agent/AgentHeader.tsx, Rail.tsx, styles, canonical locales and pane-header regression scenarios`.
- [x] `S03` - Add true fullscreen controls with restoration and verify the integrated workspace; `native/desktop/src-tauri/src/shell/window_controls.rs, frontend Host contract and adapters, Titlebar.tsx, scenarios and native window tests`.

## Parallelization

Sequential implementation by CADRUMO-WINDOWMANAGER. CADRUMO-FRONTEND retains its five reported files. It explicitly handed build/test ownership to CADRUMO-WINDOWMANAGER; no overlapping runs. The canonical browser dev server stays running for user inspection.

## Verification

Verify unique identities and validated restoration, directional split/tab/swap transitions, retained mounted content, keyboard resizing, drag/drop, native fullscreen command parity and exit behavior. Run frontend checks and browser scenarios plus applicable Rust checks through the enrolled build tree. Record blocked native evidence separately. Review the integrated change before completion.
