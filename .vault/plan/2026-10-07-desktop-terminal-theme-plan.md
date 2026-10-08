---
tags:
  - '#plan'
  - '#desktop-terminal-theme'
date: '2026-10-07'
tier: L1
related:
  - '[[2026-10-04-desktop-shell-adr]]'
  - '[[2026-10-05-desktop-design-system-adr]]'
  - '[[2026-08-11-tui-interface-adr]]'
modified: '2026-10-07'
body_schema: body-v2
body_hash: 'sha256:35943c7bec634ec51131f2782e00d49918967bd72adaa954d64ad8de5ede2a2f'
---

# `desktop-terminal-theme` plan

## Description

Approved 2026-10-07. The user explicitly requests desktop theme switching to restyle the embedded TUI and shells. Apply the desktop-shell presentation ownership, desktop-design-system ANSI palette exception, and tui-interface component ownership. Refine the desktop-shell decision for the embedded ANSI palette and narrowly scoped TUI appearance request. No Settings, runtime authority, shell command injection, or process restart.

## Steps

- [x] `S01` - Make embedded TUI and shell palettes follow desktop appearance without restarting sessions; `native/desktop/frontend/src, native/desktop/frontend/tests, native/desktop/src-tauri/src/terminal, src/cadrumo/entrypoints/tui/components, src/cadrumo/entrypoints/tui/tests, native/CONTRACT.md`.

## Parallelization

Root owns S01 and all shared verification. Independent read-only final review may be delegated to the existing startup_review agent after implementation; it owns no source edits.

## Verification

Python rendering and standalone theme tests; browser tests for live recoloring of real Textual output and shell output, including hidden panes and stable sessions. Frontend lint, format, types; scoped Python lint and types; native launch regression tests and build. Report session 1 visual acceptance as unavailable from session 0.
