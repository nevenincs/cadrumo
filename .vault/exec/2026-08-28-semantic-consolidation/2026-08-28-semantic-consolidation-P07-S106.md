---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:193c9c5a443b4ce78271d6306e4210e8e30fe6c927a6f5dc2d45c87f79bd10c8'
step_id: 'S106'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Finish the errors hierarchy split the concurrent session left half-landed, repointing the five stragglers still reaching the namespace

## Scope

- `src/cadrumo/core/errors/`

## Changes

- `M` `src/cadrumo/core/errors/__init__.py`
- `M` `src/cadrumo/application/evidence/_models.py`
- `M` `src/cadrumo/core/tests/test_setup_answers.py`
- `M` `src/cadrumo/domain/calculations/registry/errors.py`
- `M` `src/cadrumo/domain/fincas/errors.py`
- `M` `dev/tests/test_authored_error_message_join.py`
- `verify:` `pytest src/cadrumo/core/errors -n 0 -m ""` -> `pass` (one pre-existing failure, see Notes)

## Notes

The split had been reverted, then re-landed by the concurrent session, which
deleted the three private modules and kept 365 repointed consumers but left the
namespace still exporting. Restoring that namespace from HEAD was the wrong
read of the state and broke the tree; the working tree wanted the inert form and
five stragglers repointed.

`test_exception_base_hygiene` still reports four production exception classes
rooting at bare builtins without a declared rationale. Those classes arrive from
peer commits and this Step's diff to their files is empty.
