---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:13b0df8f71190160cc84ad084ea5ce324618be0c6f2bbe34a4b2885affcd7308'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# `tui-architecture` audit: `W08.P27.S379 Review`

## Scope

Read-only review of S379 commits `8705132387`, `6fff2f1555`, `643a38d922`, prior remediation commits `257015ff7260`, `e4170744abf7`, `e26a5f5c2a`, and `11107a48b5`, locale remediation commits `fdf50282b9`, `e14bc2e9a9`, `d691a54528`, and `e58a4a2ca7`, and final fixture remediation `3943d6d234`. The review rechecked the six-route workspace, protected-data and action-handoff boundaries, supported locale namespace/key and placeholder parity, live four-locale rendering, and the focused application and TUI suites.

## Findings

### aeat-sync-operator-copy-is-hard-coded | high | Every production AEAT Sync screen bypasses the locale catalogue

Resolved in `e26a5f5c2a`: headings, navigation and data-table columns, action labels, unavailable/refusal notices, operation lifecycle status, enum labels, and the missing-value glyph now resolve through the AEAT Sync locale namespace rather than direct screen literals.

### route-and-action-tests-do-not-exercise-rendered-public-rows | medium | The focused suite proves empty routing but not rendered source or operation behavior

Resolved in `e26a5f5c2a`: the focused suite constructs valid nonempty public projection records, mounts every declared route, asserts redaction sentinels are absent, tests one-shot host handoff and no mount-time callback, rejects an unknown action-operation join, refuses unread notification access, and exercises all supported locale status keys.

### aeat-sync-es-ca-catalogues-copy-english-source-text | high | Complete locale keys do not provide real Spanish and Catalan operator translations

Resolved in `fdf50282b9`, `e14bc2e9a9`, and `d691a54528`. The four `tui.aeat_sync` catalogues contain exactly 111 matching keys with complete placeholder parity. Spanish retains only five intentional invariant or non-prose equalities and Catalan only nine: the declaration transport format, AEAT, lexical cognates, template forms, and the missing-value glyph. All other Spanish and Catalan entries differ meaningfully from English, including visible headings, actions, source states, availability, refusals, and operation failure.

### notification-selection-contract-breaks-s379-focused-tui-suite | high | The hardened public projection makes six claimed focused TUI tests fail before mount

Resolved in `3943d6d234`: the S379 fixture now enters through `project_aeat_sync_workspace` using scoped facts and lets the public projector derive the mandatory opaque notification selection key. All relevant S397 and S379 tests pass, including six mounts, redaction, source/refusal, action-handoff, and semantic notification-focus behavior.

### aeat-sync-hu-catalogue-retains-english-operator-copy | high | Hungarian has key parity but not complete real translation coverage

Resolved in `e58a4a2ca7`. The complete namespace has 111 matching keys and placeholder parity in every supported locale. Hungarian now retains only four intentional invariant or non-prose equalities: AEAT, the declaration template form, source interpolation templates, and the missing-value glyph. The six live Hungarian screen titles, action/refusal text, and semantic labels render authored Hungarian copy rather than English source values.

## Positive findings

The internal route catalogue covers the six declared zones exactly once. The controller accepts only a singleton action-operation pair that matches both the canonical action catalogue and an injected public operation contract with TUI frontend admission; unknown, ambiguous, unregistered, and host-absent paths visibly fail closed. The application projection retains protected-data stripping and safe notification-key construction. The six screens mount one nonempty public row each for every supported locale; source availability, local/AEAT state, discrepancy, redaction, and no mount-time host callback remain covered. The TUI package imports only safe projection and operation identifiers, with no adapter, persistence, filesystem, browser, network, calculation, or business implementation authority. Escape dismisses the child rather than the application. Ruff format, Ruff lint, ty, and basedpyright pass, as do all 26 focused application-plus-TUI tests.

## Recommendations

1. Retain the complete four-locale namespace and placeholder-parity checks. Add a parameterized mounted-screen locale test for all six screens so future changes prove semantic visible labels, action/refusal states, and operation failure copy remain localized while route identities and row keys stay invariant.
