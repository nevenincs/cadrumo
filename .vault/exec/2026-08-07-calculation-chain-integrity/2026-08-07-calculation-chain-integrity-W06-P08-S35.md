---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:69fa7e438ab22f89580c9892c530ba77bc81f3789804f7d89b2946fa3b22e7af'
step_id: 'S35'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` exec W06.P08.S35

## Outcome

Answered: no. An invoice with no declared operation type cannot legitimately need any of the five claves the category fallback does not emit, so the fallback IS correct by scope, and now says so at the declaration.

## The answer, by clave

`_CLAVE_BY_KIND_AND_CATEGORY` (`application/invoices/_source_resolver.py:121`) carries four entries plus triangulation handled separately, and the comment above it records why the other five are unreachable rather than missing:

- **M / H** (supplies following an exempt importation, LIVA art. 27.12) share the intra-community supply category with **E**, so no category predicate can separate them. The operator states these via the operation type, and the resolver discloses the ambiguity rather than guessing.
- **R / D / C** (the call-off stock claves) report movements carrying no invoice at all, so no invoice-sourced path can reach them by construction.

Two different reasons, and the distinction matters: the first is a genuine ambiguity the fallback cannot resolve, the second is out of scope for any invoice-sourced path whatsoever. Conflating them would suggest the second is also a gap worth closing.

## Why the comment placement matters

It sits on the table itself, so a reader who finds four entries where the enum has ten meets the reason immediately. Without it the natural reading is "this table is incomplete", and the natural fix, widening it, would change what gets declared rather than how it is expressed.
