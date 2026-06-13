---
tags:
  - '#exec'
  - '#no-synthetic-sede-live-surfaces'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S02'
related:
  - '[[2026-05-26-no-synthetic-sede-live-surfaces-plan]]'
---

# `no-synthetic-sede-live-surfaces` `P01.S02`

Added guard-policy validation for AEAT-hosted runtime policies.

- Modified: `src/aeat/domain/calculations/registry/_remote_state_guard.py`
- Created: `src/aeat/domain/calculations/registry/_aeat_hosts.py`

## Description

`RemoteStateGuardPolicy` now rejects AEAT-hosted policies with
`synthetic_data_allowed = true` before any remote operation can be preflighted.
The runtime guard shares the same AEAT host predicate used by the registry
schema so the policy layer and declaration layer cannot drift.

## Tests

Covered by `test_remote_state_guard.py` and the neighboring Sede driver policy
tests recorded in `P03.S07`.
