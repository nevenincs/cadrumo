---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:da0237aed101c3166dc9dfb1ad5b55f7c0ea6d75cdbb01dacfb422b698f59b36'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# `tui-architecture` audit: `W08.P27.S379 Review`

## Scope

Read-only review of S379 commits `8705132387`, `6fff2f1555`, and `643a38d922` against the approved plan, navigation decision, hardened S397 public projection, route/controller/screens, focused tests, and execution record. The review covered six-route totality, source and protected-data truth, explicit operation handoff, host-neutral lifecycle, accessibility, localization, static quality, and targeted duplication evidence.

## Findings

### aeat-sync-operator-copy-is-hard-coded | high | Every production AEAT Sync screen bypasses the locale catalogue

Headings, navigation and data-table columns, action labels, unavailable/refusal notices, operation lifecycle status, and the missing-value glyph are authored directly in English. `_label` also exposes raw enum spellings rather than localized operator meanings. This violates the existing TUI localization contract and makes the new workspace unusable as a shipped four-locale surface.

### route-and-action-tests-do-not-exercise-rendered-public-rows | medium | The focused suite proves empty routing but not rendered source or operation behavior

The test projection is built with `model_construct`, empty rows, and empty source observations. It verifies route-table totality and the controller pair allowlist, but never mounts each of the six concrete screen bodies with real sanitized rows, source availability/freshness distinctions, redaction sentinels, or an operation button invoking the exact host handoff once. The test therefore cannot catch a row-level source collapse, protected display leak, or button wiring regression.

## Positive findings

The internal route catalogue covers the six declared zones exactly once. The controller accepts only the three closed action-to-operation pairings and refuses ambiguous or read-only axes. The TUI package imports only safe application projection and operation identifiers, with no adapter, persistence, filesystem, browser, network, calculation, or business implementation authority. Escape dismisses the child rather than the application. Ruff, ty, and basedpyright pass; the targeted duplication scan reports no clones.

## Recommendations

1. Add authored locale keys for every AEAT Sync heading, column, availability/source/status label, action, refusal, operation lifecycle message, and empty glyph; replace direct strings and enum spellings with locale resolution.
2. Add six mounted-screen integration fixtures with safe nonempty rows and differing source states. Assert protected sentinels are absent, each public axis renders distinctly, unavailable zones refuse visibly, and each approved action button invokes the exact injected host request once while all other actions render no mutation control.
