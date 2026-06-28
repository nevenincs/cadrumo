---
tags:
  - '#exec'
  - '#test-topology-refactor'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S06'
related:
  - '[[2026-06-05-test-topology-refactor-plan]]'
---

# `test-topology-refactor` `W01.P02.S06`

## Scope

Underscore-prefixed test module rename.

## Description

- Renamed underscore-prefixed CLI envelope and privacy tests while moving them into the CLI test harness.
- Verified no `_test_*.py` path remains under `src/aeat`.

## Outcome

- `fd --type file '^_test_.*\.py$' src/aeat` reports 0 files.

## Notes

- The pytest discovery pattern still needs to be tightened in the later discovery step.
