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
body_hash: 'sha256:c776b657a81ae94b8536999ba14a5857498f46df6542577c07d83346211313fa'
---

# `desktop-frontend-coherence` plan

## Description

Approved 2026-10-09

The user's frontend audit and centralization request authorizes S01. Keep React, Radix, Tailwind, generated palette ownership, host boundaries, localization and stable acceptance selectors under the linked desktop design-system and desktop-shell decisions. No new dependency or public protocol decision is needed. Centralize stylesheet placement and fixed dimensions, extract presentation and subscription modules by responsibility, document naming and add drift enforcement. Preserve concurrent installation changes, including SignIn.tsx's public path. Semantic discovery was unavailable (index_unverifiable); targeted source and decision reads supplied grounding.

## Steps

- [x] `S01` - Centralize frontend styles and tokens, extract focused presentation modules, and enforce conventions with lint and browser checks; `native/desktop/frontend`.

## Parallelization

Execute S01 serially in this session. Other sessions own runtime and installation behavior; shared files are re-read and only this session's hunks are staged.

## Verification

TypeScript, ESLint, scoped Prettier, frontend guard negative fixtures, production build, Storybook build, and the full product and scenario browser suites pass. Review checks token ownership, import direction, stylesheet entry scanning, font paths and unchanged stable selectors. Browser evidence does not establish native installation or interactive host behavior.
