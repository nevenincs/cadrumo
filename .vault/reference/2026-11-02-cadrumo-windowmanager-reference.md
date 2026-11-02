---
tags:
  - '#reference'
  - '#cadrumo-windowmanager'
date: '2026-11-02'
modified: '2026-11-02'
body_schema: 'body-v2'
body_hash: 'sha256:b6f19f9a76b9aff204342c339e516d1b5f4a8b89da7a2e28f90c9816ee93b842'
related: []
---

# `cadrumo-windowmanager` reference: Docking integration

## Summary

Static inspection on 2026-11-02 of the frontend worktree before implementation. `native/desktop/frontend/src/shell/layout.ts` owns presentation persistence and validation. `native/desktop/frontend/src/App.tsx` composed the fixed agent column, docs/TUI split and bottom panel. Existing page navigation shares the docs area and its leave guards. `native/desktop/frontend/src/components/PaneHeader.tsx` composes shared pane controls. `native/desktop/frontend/src/components/ui/resize-handle.tsx` supplies pointer and keyboard resizing. Geometry can change around stable pane children without moving their React ancestry; splits must move identities rather than instantiate content again.

`native/desktop/src-tauri/src/shell/window_controls.rs` restricts controls to the main window and reports fullscreen through its token-checked Host port. Before this change the action enum lacked fullscreen entry/exit. `native/desktop/frontend/src/components/Titlebar.tsx` owns the sole presentation subscription. Native satellite windows require extending the authority and lifecycle boundary; in-app floating presentation does not.

## Discovery limits

Semantic discovery could not run because client 0.6.0 and service 0.6.4 disagree. Governing decision discovery used owning-verb ADR listings and targeted source reads. The desktop-shell, design-system and titlebar ADRs cover the implementation, with scoped November 2 amendments for dockable presentation and fullscreen controls.
