---
tags:
  - '#exec'
  - '#core-authority'
step_id: S78
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
---

# core-authority W08.P22.S78 - remove adapter imports from application/live/_errors.py

## Outcome

Removed 2 module-scope `application→adapters` imports from `application/live/_errors.py`:

- `from ...adapters.outbound.aeat.auth import (ClaveMovilApprovalTimeoutError, ClaveMovilConfigurationError, ClaveMovilFailureMode)`
- `from ...adapters.outbound.aeat.sede import SedeError, SedeFailureMode`

Moved both imports inside `classify_live_iva_acquisition_failure` as lazy local
imports. The function uses these for `isinstance` checks and `.failure_mode`
attribute comparisons — runtime access is required and cannot be replaced by
Protocol (isinstance on Protocol does not check attribute shape).

The `_errors.py` module now imports only from `core` at module scope.

RELOC-018, Rule 2.

## Commit

`8272e4f9f` — refactor(live): W08.P22.S78 - remove adapter imports from _errors.py

## Files touched

- `src/aeat/application/live/_errors.py` — adapter imports moved to lazy local

## Verification

121 live application tests pass. `ruff check` passes with no errors.
