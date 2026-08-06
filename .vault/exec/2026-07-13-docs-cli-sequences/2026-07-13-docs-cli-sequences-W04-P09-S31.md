---
tags:
  - '#exec'
  - '#docs-cli-sequences'
date: '2026-07-13'
modified: '2026-07-13'
body_hash: 'sha256:696d9dd254fc979b12ac9e802b53da701770fb57d92e4c693b3d110b8fab259c'
step_id: 'S31'
related:
  - "[[2026-07-13-docs-cli-sequences-plan]]"
---

# Implement the hover and focus help popover keyed into cli-tree.json via one same-origin per-page fetch, opening a verb token's live help by its command-path key

## Scope

- `docs/_static/cadrumo-docs.js`

## Description

- Add the `initHoverHelp` initialiser and register it in the `ready()` bootstrap; return early when the page carries no sequence tokens.
- Derive the `cli-tree.json` URL from this script's own `src` so the fetch is same-origin and page-depth-independent, and lazily fetch the projection once per page on the first hover intent, caching the promise; a non-ok response or a fetch error resolves to no hover help with no console output.
- Build one shared popover element with `role="tooltip"`; render each command node's path, usage, help, and parameters into it with `textContent` (no markup injection from the projection), leading with the specific option's parameter when the token carries `data-option`.
- Wire mouseenter/focus to open and mouseleave/blur to close, guarding the async fetch against a moved pointer via an `intended`-token check; make every command-path token focusable with `tabindex="0"`, toggle on tap for touch, dismiss on Escape, and keep exactly one popover open at a time.
- Position the popover under the token, flipping above when there is no room below and clamping horizontally within the viewport.

## Outcome

Hovering or focusing a verb or option token in a rendered sequence opens a popover with that command path's live help resolved from the per-page `cli-tree.json` fetch, keyed by the exact space-joined command-path string the P07 tokeniser stamps. The feature is keyboard accessible (focusable tokens, `aria-describedby` wiring, Escape to dismiss), touch-capable (tap toggles), and degrades silently when the projection is absent, leaving the static transcript unaffected. `node --check` passes; the change is purely additive (187 insertions).

## Notes

The projection is a same-origin build artifact, but the popover is still built with `textContent` rather than `innerHTML`, so a malformed help string cannot inject markup. The Escape listener is the only document-level handler and gates on the popover being visible, so it does not interfere with the Ctrl/Cmd-K palette or other keys.
