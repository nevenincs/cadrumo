---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:3e61d7b7aa93cf6e44425b5082de6cff5406f2bec703051167a72816660c9381'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# `tui-architecture` audit: `W08.P27.S379 Review`

## Scope

Read-only review of S379 commits `8705132387`, `6fff2f1555`, `643a38d922`, and remediation commits `257015ff7260`, `e4170744abf7`, `e26a5f5c2a`, and `11107a48b5` against the approved plan, navigation decision, hardened S397 public projection, route/controller/screens, focused tests, locale catalogues, and execution record. The review covered six-route totality, source and protected-data truth, explicit operation handoff, host-neutral lifecycle, accessibility, localization, static quality, and targeted duplication evidence.

## Findings

### aeat-sync-operator-copy-is-hard-coded | high | Every production AEAT Sync screen bypasses the locale catalogue

Resolved in `e26a5f5c2a`: headings, navigation and data-table columns, action labels, unavailable/refusal notices, operation lifecycle status, enum labels, and the missing-value glyph now resolve through the AEAT Sync locale namespace rather than direct screen literals.

### route-and-action-tests-do-not-exercise-rendered-public-rows | medium | The focused suite proves empty routing but not rendered source or operation behavior

Resolved in `e26a5f5c2a`: seven focused tests now construct valid nonempty public projection records, mount every declared route, assert redaction sentinels are absent, test one-shot host handoff and no mount-time callback, reject an unknown action-operation join, refuse unread notification access, and exercise all supported locale status keys.

### aeat-sync-es-ca-catalogues-copy-english-source-text | high | Complete locale keys do not provide real Spanish and Catalan operator translations

The exact `tui.aeat_sync` key sets now match across `en`, `es`, `ca`, and `hu`, and Hungarian contains authored copy. However the Spanish and Catalan entries for visible headings, actions, source states, availability, columns, refusals, and operation failure remain verbatim English (for example `Review census`, `Operation could not be started.`, and `This source is unavailable for viewing.`). The live locale contract requires a real translation for every required key and explicitly says that copying source text does not satisfy coverage. Strict key-resolution checks cannot detect this defect, so the surface still fails localization readiness.

## Positive findings

The internal route catalogue covers the six declared zones exactly once. The controller accepts only a singleton action-operation pair that matches both the canonical action catalogue and an injected public operation contract with TUI frontend admission; unknown, ambiguous, unregistered, and host-absent paths visibly fail closed. The six concrete screens mount valid nonempty public rows and retain independent local, AEAT, freshness, availability, and discrepancy axes. Protected admission fields are stripped before projection construction and focused mount coverage checks representative protected sentinels. The TUI package imports only safe projection and operation identifiers, with no adapter, persistence, filesystem, browser, network, calculation, or business implementation authority. Escape dismisses the child rather than the application. Ruff, ty, and basedpyright pass; the targeted duplication scan remains clean.

## Recommendations

1. Replace every English placeholder value in the Spanish and Catalan `tui.aeat_sync` namespace with reviewed, idiomatic Spanish and Catalan translations, retaining only invariant transport identifiers such as AEAT, Modelo codes, action IDs, and date/period values.
2. Add a parameterized mounted-screen locale test for all six screens and all four supported locales. It must assert a semantic visible label, action/refusal state, and operation failure message change from English for Spanish, Catalan, and Hungarian while route identities and row keys remain invariant. Keep a structural key-set and placeholder-parity assertion for the complete namespace.
