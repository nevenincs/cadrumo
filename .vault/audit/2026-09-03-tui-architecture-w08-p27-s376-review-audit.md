---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:0c98010346b82991a0b6f7e5e2f114878bd2ed7d4a97fad3d6cefc21a3e50a0f'
related:
  - '[[2026-08-11-tui-architecture-plan]]'
  - '[[2026-09-02-unreachable-capability-tui-navigation-join-adr]]'
---
# `tui-architecture` audit: `W08.P27.S376 host-neutral Modelo route review`

## Scope

Independent review of the live W08.P27.S376 host-neutral refactor across the Modelo work picker, bounded review, six read-workspace destinations, editor return path, generic host access, focused compositor tests, typing, and locale coverage. The review probed standalone return parity, generic root mounting and callback settlement, dismiss-only behavior, focus restoration, unsaved-edit admission, route completeness, and concrete-host coupling.

## Findings

No open high, medium, or low finding remains.

## Disposition evidence

The work picker remains usable through its standalone `ModeloWorkSelectApp` host while the underlying `ModeloWorkSelectScreen` returns the same semantic work-unit identity through `dismiss`. A mounted generic `App[None]` test selects a non-default row, receives that exact identity through the caller callback, returns to the original root screen, and restores the previously focused root control.

The bounded review likewise keeps its standalone `ModeloWorkReviewApp` host and uses the same mountable `ModeloWorkReviewScreen`. Escape dismisses only the review screen with `None`; the generic root receives one callback, remains running, and regains its exact prior focus.

All six workspace read destinations remain present in the exact closed destination catalogue. Overview, inputs, results, provenance, filing, and verification each implement their quit binding with `dismiss(None)`. Their parameterized generic-root compositor test proves callback settlement, root survival, and exact focus restoration. No production Modelo screen invokes application exit.

The editor's Escape path consults `review_gate().leaving_with_unsaved_changes()`. Dirty staged input leaves the child mounted, preserves its touched state, emits no callback, and does not restore root focus prematurely; a clean editor dismisses normally. The screen does not duplicate or reinterpret the application-owned dirty-state rule.

Modelo screens use generic typed application access and `Screen` result types rather than narrowing to the installed application class. The two small `ScreenHostApp` subclasses are standalone composition wrappers, not dependencies of the screens or route factories. The six-destination catalogue remains total and unique, and the picker outcome names the routed overview destination. Existing all-locale compositor coverage mounts every workspace destination in Spanish, English, Catalan, and Hungarian; editor locale mismatch is rejected before input can be parsed under a different locale.

## Verification

Ruff passed over the complete Modelo TUI package. ty passed over the complete Modelo TUI package. Direct source inspection found six read-workspace quit handlers and six `dismiss(None)` implementations, no production `self.app.exit`, and no concrete installed-App narrowing. The deadline-limited focused compositor run produced passing cases and no failure before it was stopped at the review coordinator's request; the exact generic-root, callback, focus-restoration, standalone-wrapper, and editor-unsaved assertions were also reviewed directly in their live tests.

## Recommendation

CLOSE. W08.P27.S376 is safe to mark complete. No high or medium issue remains.
