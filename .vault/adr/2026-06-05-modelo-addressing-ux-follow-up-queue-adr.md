---
tags:
  - '#adr'
  - '#modelo-addressing-ux'
date: '2026-06-05'
modified: '2026-10-03'
body_hash: 'sha256:a267c9699fa572d894da4cf78bcfbd2617d58ad6527227a48eeb252c64f14203'
related:
  - '[[2026-06-04-modelo-addressing-ux-adr]]'
  - '[[2026-06-04-modelo-addressing-ux-research]]'
---

# Modelo Addressing UX Follow-Up ADR Queue | (**status:** `accepted`)

## Scope and relationship to primary ADR

Queue only. This file does not supersede the accepted Modelo Addressing UX ADR.

## ADR-Required Questions

- Persistent hidden command state: any future `work use` or implicit selected-work-unit context must receive an ADR before implementation.
- Non-singleton active filing workspaces: any future design allowing multiple active work units for the same exact filing target must receive an ADR before implementation.
- Operator-facing revision switching beyond explicit stateless selectors: any new switching model that changes `--select current`, `latest-draft`, `latest-verified`, `filed`, or explicit id semantics must receive an ADR before implementation.

## Plan-Only Follow-Ups

- Continue decomposing residual `_modelo.py` command bodies into focused CLI modules that consume application facades.
- Keep lowering `_modelo.py` and command-function size budgets after each extraction.
- Preserve raw ids as advanced exact-addressing escape hatches, not the common operator path.

## Current Disposition

No additional ADR is required for the implemented natural-key modelo work addressing, resume compatibility, export addressing, or centralized operator-target facade. Those decisions are covered by the accepted Modelo Addressing UX ADR and this execution plan.
