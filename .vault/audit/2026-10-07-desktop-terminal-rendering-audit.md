---
tags:
  - '#audit'
  - '#desktop-terminal-rendering'
date: '2026-10-07'
modified: '2026-10-07'
body_schema: 'body-v2'
body_hash: 'sha256:ff5aea85be3207ab273b4d64c7799efe9bd45e9a8459fe6a3d002a0e3448cbe5'
related:
  - "[[2026-10-07-desktop-terminal-rendering-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace desktop-terminal-rendering with a kebab-case feature tag, e.g. #foo-bar.
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

# `desktop-terminal-rendering` audit: `Embedded terminal cell and border rendering`

## Scope

<!-- What was audited and why -->

## Findings

<!-- A rolling log of findings: append one subsection per finding, grouped or ordered by
     severity, using the heading form

       ### Embedded terminal cell and border rendering | {level} | {summary}

     followed by a paragraph carrying the detail. Embedded terminal cell and border rendering is a concise kebab-case slug,
     {level} is the severity (critical, high, medium, low), and {summary} is a one-line
     statement. Append continuously as findings surface; do not rewrite settled entries. -->

## Recommendations

<!-- Actionable recommendations, each tied to a finding above. An
     architecturally significant recommendation names the decision a
     follow-on ADR must make; the decision itself is never recorded here. -->

## Context

## Scope

User-reported cumulative column drift and spikes around embedded TUI borders. Reviewed the production React/xterm setup, bundled font declarations, renderer lifecycle and focus/resize interactions under the accepted desktop-shell architecture. Independent review PASS after the delayed-focus correction.

## Findings

### font-metrics | medium | Resolved cached fallback widths during cold startup

TerminalPane opened xterm synchronously while both JetBrains Mono font-face subsets used font-display swap. xterm's DOM WidthCache cached fallback glyph measurements. A controlled delayed-font browser reproduction placed equal-column markers 22.5 CSS pixels apart across long rows. Loading every matching FontFace before opening xterm resolves the stale-cache defect. A failed subset selects a system-only stack so late partial font loading cannot change metrics afterward. Upstream evidence: xtermjs/xterm.js addons/addon-web-fonts/README.md, read 2026-10-07, documents this same preload requirement.

### renderer-geometry | medium | Resolved DOM rounding and font-drawn TUI borders

After fonts were ready, the original DOM renderer still accumulated 1 to 1.5 CSS pixels of width difference across 120 cells at small/large sizes. It rendered box characters through fallback fonts and used lineHeight 1.15. The pinned official WebGL addon now positions cells explicitly, draws custom box/block glyphs, uses unit line height and rescales overlapping glyphs. Initialization failure or unrecovered context loss returns to the DOM renderer without restarting the PTY. The pinned addon only detaches its canvas on disposal, so the shell releases its existing browser GL context to prevent context accumulation across TUI restarts. DOM fallback retains its precision limitations; it preserves usability when graphics is unavailable.

### hidden-resize | medium | Resolved invalid fitting while a pane is hidden

Font-size effects previously fitted unconditionally, including display-none panes. Fitting now requires nonzero dimensions and its animation frame is cancelled on cleanup. Browser test confirms hidden font changes preserve the PTY grid until shown, then refit without reopening.

### delayed-focus | medium | Resolved first-open focus expiration

Independent review found that font readiness could exceed the App focus wish's one-second timeout. Pending terminal readiness now preserves that wish while subsequent pointer/key input still cancels it. A 1200ms blocked-font focus test and a later-input cancellation test pass.

### verification | low | Passing browser and build evidence with live-session limitation

Eighteen rendering tests and 26 existing desktop tests have applicable passing evidence across focused runs. Tests use real production frontend assets, real xterm and the real Tauri transport adapter with deterministic fake PTY bytes. Pixel checks verify column alignment below one CSS pixel for four font sizes at actual Chromium display scales 1, 1.25 and 1.5 before/after resizing; a border test verifies continuous vertical strokes without protrusions. GPU unavailability, context loss, font failure, hidden fitting and delayed focus are covered. The first 42-test run passed 41; its remaining test used an incorrect accessible role, corrected to radiogroup and passed. Four changed/additional tests then passed; the final 14 focus/interaction tests also passed. Context-only Playwright DPR emulation disagreed with ResizeObserver physical pixels, so scale tests also launch Chromium with the matching force-device-scale-factor; no renderer measurements are mocked. TypeScript, scoped ESLint, Prettier and diff whitespace checks pass. The Debug Tauri host rebuilt successfully at build/desktop-windows-x64/cargo/desktop/debug/cadrumo.exe. Session 1 visual acceptance is not claimed; the running installation was not replaced.

### checkpoint | low | Concurrent Git index lock prevents commits

The worktree index.lock remained owned outside this task. No lock was removed and no unrelated edits were staged. Implementation and verification records remain in the working tree.

## Recommendations

Use a newly assembled matching package in session 1 to confirm the observed border artifacts are gone on its WebView2/GPU combination. The tested fixes address reproduced renderer defects; unspecified artifacts in live TUI content require that visual acceptance.
