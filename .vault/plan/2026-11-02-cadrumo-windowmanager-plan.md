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
body_hash: 'sha256:5b0e235983847cfe50169f83d0cc0a7718a875c4abd700a40569eff550e05378'
---

# `cadrumo-windowmanager` plan

## Description

Approved 2026-11-02. The user requested implementation of dockable, tabbed panels with directional splits, swapping, expansion, true fullscreen, floating and single-instance enforcement. Preserve CADRUMO-FRONTEND's five owned files. The desktop-shell and desktop-titlebar amendments govern presentation persistence, retained mounted content, and main-window fullscreen operations. The design-system ADR governs primitives, tokens and localization. Floating panes remain inside the main window, as communicated while awaiting the optional clarification about native secondary windows.

## Steps

- [x] `S01` - Implement validated single-instance docking layout state and migration; `native/desktop/frontend/src/shell/docking.ts (new), shell/layout.ts and focused layout tests`.
- [ ] `S02` - Integrate tab groups, directional splitting, dragging, swapping and floating presentation; `native/desktop/frontend/src/App.tsx, components/docking (new), Rail.tsx, pane headers, styles and canonical locales`.
- [ ] `S03` - Add true fullscreen controls with restoration and verify the integrated workspace; `native/desktop/src-tauri/src/shell/window_controls.rs, frontend Host contract and adapters, Titlebar.tsx, scenarios and native window tests`.

## Parallelization

Sequential implementation by CADRUMO-WINDOWMANAGER. CADRUMO-FRONTEND retains its five reported files. It explicitly handed build/test ownership to CADRUMO-WINDOWMANAGER; no overlapping runs. The canonical browser dev server stays running for user inspection.

## Verification

Verify unique identities and validated restoration, directional split/tab/swap transitions, retained mounted content, keyboard resizing, drag/drop, native fullscreen command parity and exit behavior. Run frontend checks and browser scenarios plus applicable Rust checks through the enrolled build tree. Record blocked native evidence separately. Review the integrated change before completion.
