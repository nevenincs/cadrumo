---
tags:
  - '#reference'
  - '#cadrumo-windowmanager'
date: '2026-11-02'
modified: '2026-11-02'
body_schema: 'body-v2'
body_hash: 'sha256:af829e5147d840a5c17e9cf24d2dddaf00dcf9a3d66dd1807155c7806e102f22'
related: []
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #reference) and one feature tag.
     Replace cadrumo-windowmanager with a kebab-case feature tag, e.g. #foo-bar.
     Exactly these two tags are allowed; do not append additional tags.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - Cite code as inline backtick locators: `src/module.py:42`; never as a
       markdown link. -->

# `cadrumo-windowmanager` reference: `Docking integration`

<!-- Brief description of what was researched and what sources were consulted.

Include any concrete references to files, line numbers, modules, etc. This is
the information that coding agents will consult during implementation. -->

## Summary

<!-- Findings pertinent to `cadrumo-windowmanager` being considered. Include implementation
details and architecture overviews considered insightful, essential, or
relevant. Adapt format to content. -->

## Context

# CADRUMO-WINDOWMANAGER reference

## Summary

Static inspection on 2026-11-02 of the frontend worktree. `native/desktop/frontend/src/shell/layout.ts:85` owns presentation state and validates stored layout at `:245`. `native/desktop/frontend/src/App.tsx:628` derives visibility from four areas; `:3460` composes a fixed agent column, docs/TUI split and bottom panel. Existing page navigation shares the docs area and its guards. `native/desktop/frontend/src/components/PaneHeader.tsx:48` composes shared pane controls. `native/desktop/frontend/src/components/ui/resize-handle.tsx:33` supplies pointer and keyboard resizing. Geometry can change around stable pane children without moving their React ancestry. Splitting a panel must move its identity, not instantiate its content again.

`native/desktop/src-tauri/src/shell/window_controls.rs:117` refuses non-main windows. `:127` reports fullscreen, but Action at `:50` lacks fullscreen entry/exit. Supported Rust window calls are already relayed through a token-checked Host port. `native/desktop/frontend/src/components/Titlebar.tsx:43` owns the sole presentation subscription, which cannot be independently replaced by a docking component. Native satellite windows would require extending the main-only authority/lifecycle design; an in-app floating presentation would not.

Semantic discovery could not run because client 0.6.0 and service 0.6.4 disagree. Decision discovery used owning-verb ADR listings and targeted source reads.
