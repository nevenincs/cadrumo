---
tags:
  - '#exec'
  - '#exception-restructure'
date: '2026-05-09'
modified: '2026-05-09'
related:
  - '[[2026-05-09-exception-restructure-phase-1-plan]]'
---

# `exception-restructure` `phase-1` `step-1`

Batch 1 exception migration.

- Modified: `src/aeat/core/errors/__init__.py`
- Modified: `src/aeat/adapters/outbound/google/__init__.py`
- Modified: `src/aeat/entrypoints/cli/_tty.py`
- Created: None (Removed some `_errors.py` files eventually)

## Description

Migrated the following exception classes to `src/aeat/core/errors/__init__.py`:
- `GoogleAuthUnavailableError` from `aeat.adapters.outbound.google`
- `DeadlineError`, `ProfileError`, `ScheduleComputationError` from `aeat.domain.deadlines`
- `NonTtyRefusedError` from `aeat.entrypoints.cli._tty`
- `WorkflowError`, `WorkflowComponentError`, `WorkflowAbortedError`, `WorkflowAbortSignal` from `aeat.application.workflow`
- `SanitizationError`, `SanitizerSourceParseError`, `SignaturePresentError`, `AlreadySanitizedError`, `UnknownSurfaceError` from `aeat.adapters.inbound.sanitizer`

## Tests

Pending boundary test.
