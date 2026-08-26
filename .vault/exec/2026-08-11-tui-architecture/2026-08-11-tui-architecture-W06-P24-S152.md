---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:bdef768092ba1ed9b1392049605b3b374e658ea5b2a550e98fc763bd31ebf175'
step_id: 'S152'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Enroll modelo.work.verify through the existing verify_modelo_revision authority with exact capability evidence, progress and REVIEW declarations, guarded persistence and event effects, safe result receipt, and typed Workspace refresh target

## Scope

- `src/cadrumo/application/modelo/_operation_definitions.py and src/cadrumo/application/modelo/_verification_actions.py`

## Changes

- `M` `src/cadrumo/application/modelo/operation_definitions.py`
- `M` `src/cadrumo/application/modelo/tests/test_work_rename_operation.py`
- `M` `.vault/plan/2026-08-11-tui-architecture-plan.md`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_work_rename_operation.py -n0` -> `pass` (18)

## Notes

The request carries the revision to verify and deliberately NOT the taxpayer
profile the gates are judged against. That profile is resolved at execution
from live state through an injected resolver, so a request replayed later
cannot verify against a profile the taxpayer has since changed, and the
entrypoint keeps ownership of how the profile is obtained.

The public result reports outcome and counts rather than casilla id lists: the
verification report stays the record of truth, and shipping resolved ids would
put a filing-shaped payload into an operation result.

REVIEW is declared with two progress phases (gates, persist) and cooperative
cancellation, because verification is reviewable work rather than a silent
write. The authority keeps its guarded persistence, its events and the
completeness verdict; a gate asserts the executor names none of them.
