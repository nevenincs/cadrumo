---
tags:
  - '#plan'
  - '#desktop-frontend-coherence'
date: '2026-10-09'
tier: L1
related:
  - '[[2026-10-05-desktop-design-system-adr]]'
  - '[[2026-10-04-desktop-shell-adr]]'
modified: '2026-10-09'
body_schema: body-v2
body_hash: 'sha256:a084714e7bc4ef816543638e14050987da59f25a3ae26cdd9e2a014e5803f584'
---

# `desktop-frontend-coherence` plan

## Description

Approved 2026-10-09

The user's frontend audit and centralization request authorizes S01. Their follow-up on 2026-10-09 authorizes S02 to continue auditing duplication and migrate reusable low-level helpers to coherent shared owners. Their request to align the titlebar authorizes S03 to bring the titlebar into the same stylesheet, token, naming and primitive conventions. During S03 the separate native titlebar session promoted the visual study into application composition and retired its prototype files; S03 follows that stylesheet and geometry, preserving native and account logic ownership. Keep React, Radix, Tailwind, generated palette ownership, host boundaries, localization and stable acceptance selectors under the linked desktop design-system and desktop-shell decisions. No new dependency or public protocol decision is needed. Centralize stylesheet placement and fixed dimensions, extract presentation and subscription modules by responsibility, document naming and add drift enforcement. Preserve concurrent installation changes, including SignIn.tsx's public path. Semantic discovery was unavailable (index_unverifiable); targeted source and decision reads supplied grounding.

## Steps

- [x] `S01` - Centralize frontend styles and tokens, extract focused presentation modules, and enforce conventions with lint and browser checks; `native/desktop/frontend`.
- [x] `S02` - Consolidate shared date formatting, ISO-date arithmetic, calendar entry rules and log-level ranking with caller and boundary verification; `native/desktop/frontend`.
- [x] `S03` - Align titlebar stylesheet placement, responsive tokens and shared control geometry, and verify application header rendering and frontend gates; `native/desktop/frontend`.

## Parallelization

Execute S01 through S03 serially in this session. Other sessions own runtime and installation behavior; shared files are re-read and only this session's hunks are staged.

## Verification

TypeScript, ESLint, scoped Prettier, frontend guard negative fixtures, production build, Storybook build, and the full product and scenario browser suites pass. Review checks token ownership, import direction, stylesheet entry scanning, font paths and unchanged stable selectors. Browser evidence does not establish native installation or interactive host behavior.

S02 verification covers shared date/parser and formatter boundaries, calendar rules, log-level ranking, actual calendar/log browser consumers, TypeScript, ESLint, import-guard negative fixtures, scoped formatting and production/catalogue builds. The complete frontend check is still run; any unrelated concurrent prototype drift is reported without weakening the guard or changing the other session's files.

S03 final verification covers the application header at wide and narrow widths, constrained profile clipping and menu focus, shared header/window-control geometry, no prototype stylesheet leakage, TypeScript, ESLint, all ten design-system guards, formatting of the changed style/test paths, production and catalogue builds. Run the complete frontend check and report unrelated formatting failures from actively edited files without staging or weakening their checks. Earlier prototype platform checks remain historical evidence. Preserve concurrent native titlebar and account work; these browser checks do not establish native window or authentication behavior.
