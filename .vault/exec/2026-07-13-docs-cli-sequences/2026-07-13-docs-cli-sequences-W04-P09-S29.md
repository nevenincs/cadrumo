---
tags:
  - '#exec'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
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
