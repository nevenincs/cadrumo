---
tags:
  - '#exec'
  - '#test-topology-refactor'
date: '2026-06-05'
modified: '2026-07-17'
body_hash: 'sha256:55c7cb1d3bd293de2c38e477815dc384c3d2d2218baa0efd8d3af4cac6fc14d2'
step_id: 'S07'
related:
  - '[[2026-06-05-test-topology-refactor-plan]]'
---

# `test-topology-refactor` `W01.P03.S07`

## Scope

Domain-owned naked tests.

## Description

- Moved domain package tests into owner-local `tests` folders.
- Preserved domain ownership by keeping tests under their existing package boundaries.

## Outcome

- Domain test files now follow the child `tests` directory topology.

## Notes

- No domain imports were rewritten in this mechanical step.
