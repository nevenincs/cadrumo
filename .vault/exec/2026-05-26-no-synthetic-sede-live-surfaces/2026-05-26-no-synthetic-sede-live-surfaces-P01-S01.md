---
tags:
  - '#exec'
  - '#no-synthetic-sede-live-surfaces'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S01'
related:
  - '[[2026-05-26-no-synthetic-sede-live-surfaces-plan]]'
---

# `no-synthetic-sede-live-surfaces` `P01.S01`

Added schema-level validation for AEAT-hosted live cross-reference declarations.

- Modified: `src/aeat/domain/calculations/registry/_schema.py`
- Created: `src/aeat/domain/calculations/registry/_aeat_hosts.py`

## Description

`LiveCrossReferenceDecision` now rejects any declaration whose `allowed_hosts`
contains AEAT-owned infrastructure while also declaring
`synthetic_data_allowed = true`. AEAT host matching is routed through the shared
`_aeat_hosts` helper, which reuses the configured AEAT host suffix and the
legacy `aeat.es` suffix required by the accepted ADR.

## Tests

Covered by the focused registry invariant suite and committed registry loading
gates recorded in `P03.S07`.
