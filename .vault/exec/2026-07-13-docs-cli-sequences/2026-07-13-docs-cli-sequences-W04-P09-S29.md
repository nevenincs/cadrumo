---
tags:
  - '#exec'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:0321bdcf733ce340569cecc8a338b6bede09185dac7a7a0cbebe39f754b66bec'
step_id: 'S29'
related:
  - "[[2026-07-13-docs-cli-sequences-plan]]"
---

# Extend the vendored widget to parse the inline JSON payload and add frame visibility toggling, prev/next/play controls, a position indicator, and full keyboard operability

## Scope

- `docs/_static/cadrumo-docs.js`

## Description

- Add the `initSequences` entry point and register it in the existing `ready()` bootstrap alongside the broadcast, nav, command-block, and palette initialisers, matching the file's IIFE / `var` / plain-function style.
- Parse the inline `script.cadrumo-sequence-payload` per sequence, reversing the directive's `<\/` escape before `JSON.parse`, and swallow a malformed payload without breaking the widget.
- Drive stepping from the DOM `div.cadrumo-frame` elements (excluding `setup` frames, which remain their own collapsed disclosure); cumulatively reveal command and result frames via the `hidden` property so no-JS shows the full transcript and the enhanced view can still reach every frame.
- Build a per-sequence controls bar with prev, play/pause, and next buttons plus an `aria-live` position indicator; wire click handlers, a play timer at a fixed interval, and disabled-edge states.
- Scope arrow-key stepping to the sequence root so it fires only when a control inside the widget holds focus and never collides with the global Ctrl/Cmd-K palette.

## Outcome

The server-rendered sequence transcript is progressively enhanced into a stepped player: each sequence carries independent state, reveals frames one step at a time behind prev/next/play controls and a live position indicator, and is keyboard operable. Without the script every frame stays visible, so content is never lost. `node --check` passes; the change is purely additive (164 insertions, no deletions).

## Notes

The widget injects no frame content; it only toggles `hidden` and an `is-active` class, keeping the single server-rendered content source authoritative per ADR D5. A single-frame sequence is left untouched (nothing to step). CSS for the controls, active highlight, and reduced-motion lands in S30.

## Addendum — playhead redesign (operator review, presentation-only)

After a live viewing of the shipped page the operator directed a presentation revision. This is a change within ADR D5's frontend contract — the D5 payload/DOM fields are untouched, so no ADR revision is needed — recorded here per the review instruction. It revises the JS (S29), the CSS (S30), and the verification pins (S32) together.

- The stepping model changed from show/hide-frames to a PLAYHEAD over a rundown: every command line is always visible. Exactly one command is active (highlighted, output shown beneath); commands after the playhead are dimmed with highlighting dropped and output suppressed; past commands stay highlighted with output collapsed for minimal density. The dim/no-highlight state is JS-applied classes (`is-active`/`is-past`/`is-future`) the CSS keys on over the same highlighted DOM — never a server-side rewrite — so the no-JS transcript stays complete and fully highlighted.
- Removed the play button and all autonomous/timed advance, and the now-dead reduced-motion autoplay branch; prev/next plus arrow keys only. `frame.hidden` toggling is gone.
- Typography aligned to the docs code styling (JetBrains Mono via `--font-stack--monospace`, 0.85rem / 1.7 line height); command lines are bold with a `$` prompt affordance, output is a lighter, left-ruled, indented block so command-vs-output is instant.
- Removed the terminal-chrome title bar (`.cadrumo-sequence::before`) that rendered the top red bar; stripped decoration to minimal density.
- Enhancement-only, XSS (`textContent`), hover-help, a11y (focus/aria/Escape), and zero-external-requests invariants are all preserved. Verified: three S32 gates green (external-request audit, wiring/implementation incl. autoplay-removal locks, real nitpicky -n -W fixture build); `node --check` clean; CSS braces balanced.
