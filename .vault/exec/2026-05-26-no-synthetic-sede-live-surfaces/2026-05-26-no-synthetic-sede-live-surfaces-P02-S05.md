---
tags:
  - '#exec'
  - '#no-synthetic-sede-live-surfaces'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S05'
related:
  - '[[2026-05-26-no-synthetic-sede-live-surfaces-plan]]'
---

# `no-synthetic-sede-live-surfaces` `P02.S05`

Rewrote Modelo 349 GROI and IXVI live-surface metadata to disallow synthetic live input.

- Modified: `src/aeat/_data/registry/aeat/modelos/349/revisions/2020-y-siguientes/live_cross_references/0002-live_cross_references.toml`
- Modified: `src/aeat/domain/calculations/registry/test_modelo_349_registry.py`

## Description

The Modelo 349 Spanish-counterparty GROI and foreign-EU IXVI bindings retain
their `authenticated_simulator` classification, host pins, allowed query
methods, and forbidden write actions. Both now declare
`synthetic_data_allowed = false`, with comments clarifying that live execution
may only carry operator-authorised non-synthetic counterparty identifiers.

## Tests

Covered by the 133-test registry gate and committed registry loader gate
recorded in `P03.S07`.
