---
tags:
  - '#exec'
  - '#test-topology-refactor'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S09'
related:
  - '[[2026-06-05-test-topology-refactor-plan]]'
---

# `test-topology-refactor` `W01.P03.S09`

## Scope

Adapter-owned naked tests.

## Description

- Moved inbound, outbound, and persistence adapter tests into owner-local `tests` folders.
- Kept adapter tests under their existing adapter boundary.

## Outcome

- Adapter test files now follow the child `tests` directory topology.

## Notes

- Live-read adapter tests were moved as topology only; no live operations were run.
