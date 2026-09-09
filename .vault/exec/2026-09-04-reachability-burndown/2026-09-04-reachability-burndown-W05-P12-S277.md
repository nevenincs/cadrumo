---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-08'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:ec62814d4740b4a714a4128a7b8688dde95d24224f178b011a51b7a823eef1fa'
step_id: 'S277'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the test-only Modelo 145 list facade and migrate meaningful persistence assertions to the identity-bound read owner; retain create, validation, transition, idempotence, and transactional history behavior, update cadence, and remeasure exact reachability.

## Scope

- `Modelo 145 communication records and focused create/transition tests`

## Changes

- `M` `src/cadrumo/application/modelo/m145_communication_records.py`
- `M` `src/cadrumo/application/modelo/tests/test_m145_communication_create.py`
- `M` `src/cadrumo/application/modelo/tests/test_m145_communication_transitions.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` exact search for deleted list facade -> `no matches`
- `verify:` focused Ruff check -> `pass`
- `verify:` focused M145 create/transition suites -> `15 passed`
- `verify:` exact reachability -> `264 unused symbols, 31 unreachable modules, 0 orphaned tests`

## Notes

The deleted list facade had only tests as callers. Tests now confirm persistence and variation through the canonical identity-bound read operation; redundant post-create enumeration assertions were removed. Registry-coordinate refusal remains covered by create and transition owners. Exact unused symbols improved from 265 to 264.
