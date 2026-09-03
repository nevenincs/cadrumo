---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:8ceded1665fbcd9b311774c6da5e98c5ef226439064e15e9d57beedf3bba6cd6'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# `tui-architecture` audit: `W08.P27.S379 Review`

## Scope

Read-only review of S379 commits `8705132387`, `6fff2f1555`, `643a38d922`, prior remediation commits `257015ff7260`, `e4170744abf7`, `e26a5f5c2a`, and `11107a48b5`, and locale remediation commits `fdf50282b9`, `e14bc2e9a9`, and `d691a54528`. The review rechecked the six-route workspace, protected-data and action-handoff boundaries, supported locale namespace/key and placeholder parity, meaningful rendered translation, and the focused application and TUI suites.

## Findings

### aeat-sync-operator-copy-is-hard-coded | high | Every production AEAT Sync screen bypasses the locale catalogue

Resolved in `e26a5f5c2a`: headings, navigation and data-table columns, action labels, unavailable/refusal notices, operation lifecycle status, enum labels, and the missing-value glyph now resolve through the AEAT Sync locale namespace rather than direct screen literals.

### route-and-action-tests-do-not-exercise-rendered-public-rows | medium | The focused suite proves empty routing but not rendered source or operation behavior

Resolved in `e26a5f5c2a`: the focused suite constructs valid nonempty public projection records, mounts every declared route, asserts redaction sentinels are absent, tests one-shot host handoff and no mount-time callback, rejects an unknown action-operation join, refuses unread notification access, and exercises all supported locale status keys.

### aeat-sync-es-ca-catalogues-copy-english-source-text | high | Complete locale keys do not provide real Spanish and Catalan operator translations

Resolved in `fdf50282b9`, `e14bc2e9a9`, and `d691a54528`. The four `tui.aeat_sync` catalogues now contain exactly 111 matching keys with complete placeholder parity. Spanish retains only five intentional invariant or non-prose equalities and Catalan only nine: the declaration transport format, AEAT, lexical cognates, template forms, and the missing-value glyph. All other Spanish and Catalan entries differ meaningfully from English, including visible headings, actions, source states, availability, refusals, and operation failure.

### notification-selection-contract-breaks-s379-focused-tui-suite | high | The hardened public projection makes six claimed focused TUI tests fail before mount

`d691a54528` requires every projected notification row to have a unique non-null opaque selection key. The S379 TUI fixture still directly constructs a notification row with no selection key and then constructs `AeatSyncWorkspaceProjectionV1`; its six screen, redaction, route, action, and refusal tests therefore fail validation before exercising their claims. The application projection suite passes, but this is not a substitute for the S379 host-neutral screen coverage. The execution record's claimed focused verification is consequently stale on the current tree.

## Positive findings

The internal route catalogue covers the six declared zones exactly once. The controller accepts only a singleton action-operation pair that matches both the canonical action catalogue and an injected public operation contract with TUI frontend admission; unknown, ambiguous, unregistered, and host-absent paths visibly fail closed. The application projection retains its protected-data stripping and safe notification-key construction. The TUI package imports only safe projection and operation identifiers, with no adapter, persistence, filesystem, browser, network, calculation, or business implementation authority. Escape dismisses the child rather than the application. Ruff, ty, and basedpyright passed before the current fixture failure; localized catalogue structure and placeholder checks pass.

## Recommendations

1. Update the S379 TUI fixture to obtain a valid notification row through the application projector, or to supply a safe opaque public selection key in a fixture that explicitly documents the already-projected boundary. Do not bypass the model validator. Re-run the focused application-plus-TUI suite and require all seven S379 tests to mount and assert their existing claims.
2. Keep a permanent parameterized locale contract for all six mounted screens and all four supported locales. Assert semantic visible labels, action/refusal states, and operation failure copy are genuinely localized while route identities and row keys stay invariant; retain the full namespace key-set and placeholder-parity checks.
