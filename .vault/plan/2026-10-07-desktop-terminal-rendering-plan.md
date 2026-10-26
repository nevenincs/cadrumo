---
tags:
  - '#plan'
  - '#desktop-terminal-rendering'
date: '2026-10-07'
tier: L1
related:
  - '[[2026-10-04-desktop-shell-adr]]'
modified: '2026-10-07'
body_schema: body-v2
body_hash: 'sha256:3672e47045a4e1ec74ea30af296404c88da1d58c826f4e408a29be6cbbb4821c'
---

# `desktop-terminal-rendering` plan

## Description

Approved 2026-10-07

The user requests diagnosis and repair of cumulative glyph spacing drift and embedded TUI rendering glitches, clarified as spikes around borders. Reuse accepted desktop-shell renderer/session ownership. Repair font readiness, cell geometry and visible resize behavior without changing runtime authority or terminal lifetime. Use the official xterm WebGL addon with DOM fallback, preserving the accepted terminal architecture. No costly new architecture choice is required.

## Steps

- [x] `S01` - Fix embedded terminal font readiness and cell rendering with regression coverage; `native/desktop/frontend/src/components/TerminalPane.tsx, App.tsx focus readiness, shell/terminalFont.ts and terminalRenderer.ts, pinned WebGL dependency, tests/terminal-rendering.spec.ts`.
- [x] `S02` - Review and document verified terminal rendering behavior; `native/CONTRACT.md and desktop-terminal-rendering audit`.

## Parallelization

The orchestrator owns implementation and checks. A code reviewer may independently inspect the completed diff without writing code or repeating shared checks.

## Verification

Reproduce delayed-font geometry failure with the actual production shell and xterm. Verify loaded fonts, equal column positions across styled text and box characters, continuous cell-aligned TUI borders, resize and hide/show retention, GPU failure/context loss, and delayed-focus readiness and cancellation. Run scoped browser tests, TypeScript, ESLint and formatting. Record browser versus real session 1 coverage explicitly.
