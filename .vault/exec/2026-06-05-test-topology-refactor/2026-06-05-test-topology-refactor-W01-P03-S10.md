---
tags:
  - '#exec'
  - '#test-topology-refactor'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S10'
related:
  - '[[2026-06-05-test-topology-refactor-plan]]'
---

# `test-topology-refactor` `W01.P03.S10`

## Scope

Entrypoint-owned naked tests.

## Description

- Moved CLI tests into entrypoint-local `tests` folders.
- Moved `_config` command tests into their local `_config/tests` harness.

## Outcome

- Entrypoint test files now follow the child `tests` directory topology.

## Notes

- CLI business logic was not edited in this step.
