---
tags:
  - '#reference'
  - '#typescript-module-size'
date: '2026-11-06'
modified: '2026-11-06'
body_schema: 'body-v2'
body_hash: 'sha256:7e6a3a8c73350b1669e411206f263884a572cab8299d0c8b20db49b1bba45802'
related: []
---

# `typescript-module-size` reference: `TypeScript callable size measurements`

This record measures the size of every callable in the desktop frontend's TypeScript, as evidence for whether a per-callable bound should accompany the module bound in `dev/quality/typescript_module_size.py`.

Source: the committed tree of the combined preview `3f0cead531`. That preview is current `feature/tui` (`47d18b53b8`) merged with the spec, fixture, O2 and size-gate branches, so every pending module split is already applied.

What was measured:

- **Files:** all 1,115 `.ts` and `.tsx` files under `native/desktop/frontend` parsed without syntax diagnostics, using the TypeScript compiler API. One file was excluded: `src/dev/ledgerFixture.ts`, which held merge-conflict markers in that preview.
- **Callables:** every function declaration, method, arrow function, function expression, constructor and accessor. A callable's span is its first to last line inclusive, and a top-level callable's span includes the callables nested inside it.
- **Components:** top-level callables with a capitalised name that contain JSX.
- **Hooks:** top-level callables named `use` followed by a capital letter.

## Summary

Line counts for top-level callables:

| set | n | p50 | p90 | p95 | p99 | max | over 100 | over 200 | over 300 | over 500 |
|---|---|---|---|---|---|---|---|---|---|---|
| product (`src/` without `src/dev`, stories) | 2405 | 13 | 110 | 192 | 516 | 985 | 256 | 114 | 65 | 27 |
| dev fixtures (`src/dev`) | 461 | 8 | 81 | 216 | 977 | 1296 | 35 | 26 | 21 | 13 |
| stories | 926 | 6 | 27 | 38 | 66 | 105 | 1 | 0 | 0 | 0 |
| tests and specs | 3086 | 17 | 46 | 63 | 110 | 418 | 38 | 4 | 4 | 0 |
| product components | 642 | 51 | 282 | 428 | 862 | 985 | 182 | 93 | 58 | 24 |
| product hooks | 183 | 45 | 186 | 271 | 745 | 775 | 45 | 16 | 5 | 3 |
| product, neither component nor hook | 1580 | 8 | 31 | 48 | 130 | 373 | 29 | 5 | 2 | 0 |

Nested callables across every class: 13,155 of them, with p50 of 2, p99 of 75 and a maximum of 377 lines.

Large callables are concentrated in two places:

- **Product components and hooks.** These include `MovementsSection` at `src/components/ledger/movements/MovementsSection.tsx:144` (985 lines), `UserProfilePage` at `src/components/profile/UserProfilePage.tsx:64` (932), `FilingCalendarView` at `src/components/FilingCalendar.tsx:86` (922), `ProrrataPane` at `src/components/ledger/setup/ProrrataPane.tsx:68` (917) and `AgentColumn` at `src/components/AgentColumn.tsx:96` (887). The largest hooks are `useMovementEditing` at `src/components/ledger/editing/MovementEditing.tsx:182` (775) and `useSignIn` at `src/shell/signIn.ts:166` (745).
- **Fixture factories.** These include `makeWrites` at `src/dev/assetsFixtureWrites.ts:60` (1296), `inventoryOperations` at `src/dev/ledgerInventoryFixture.ts:110` (1149), `fixtureAgent` at `src/dev/agentFixtureHost.ts:196` (1145) and `evidenceOperations` at `src/dev/ledgerEvidenceFixture.ts:143` (1056).

Each of these is one closure holding a component's whole state and event surface, or a fixture's whole operation table. So most modules satisfy the 1500-line bound, yet many single callables come close to it. Plain functions that are neither components nor hooks are small: p99 is 130 lines.
