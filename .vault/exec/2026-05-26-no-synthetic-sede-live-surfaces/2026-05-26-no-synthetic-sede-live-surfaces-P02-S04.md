---
tags:
  - '#exec'
  - '#no-synthetic-sede-live-surfaces'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S04'
related:
  - '[[2026-05-26-no-synthetic-sede-live-surfaces-plan]]'
---

# `no-synthetic-sede-live-surfaces` `P02.S04`

Rewrote Modelo 100 Renta WEB Open live-surface metadata and tests to disallow synthetic live input.

- Modified: `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/live_cross_references/0001-modelo-100-renta-web-open.toml`
- Modified: `src/aeat/domain/calculations/registry/test_modelo_100_registry.py`

## Description

The Modelo 100 Renta WEB Open cross-reference remains an `open_simulator`
surface, but its AEAT-hosted declaration now advertises
`synthetic_data_allowed = false` with ADR provenance. The registry test was
updated to assert the no-synthetic policy without changing the existing
read-only forbidden-action expectations.

## Tests

Covered by the 133-test registry gate and the committed registry loader gate
recorded in `P03.S07`.
