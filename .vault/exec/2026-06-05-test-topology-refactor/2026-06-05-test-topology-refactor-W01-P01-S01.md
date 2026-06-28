---
tags:
  - '#exec'
  - '#test-topology-refactor'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S01'
related:
  - '[[2026-06-05-test-topology-refactor-plan]]'
---

# `test-topology-refactor` `W01.P01.S01`

## Scope

Baseline mechanical discovery for the repository test topology.

## Description

- Logged the accepted discovery command for all Python test files under `src/aeat`.
- Logged the final topology gate command for `test_*.py` files outside `tests` directories.
- Logged invalid filename discovery commands for `_test_*.py` and `*_test.py`.

## Outcome

- `fd --type file '^(test_|_test_).*\.py$' src/aeat` reported 1054 files.
- `fd --type file '^test_.*\.py$' src/aeat --exclude tests` reported 1026 files outside `tests` directories.
- `fd --type file '^_test_.*\.py$' src/aeat` reported 2 underscore-prefixed test modules.
- `fd --type file '.*_test\.py$' src/aeat` reported 0 suffix-style test modules.
- 26 `test_*.py` files were already under a `tests` directory.

## Notes

- No test execution was run in this baseline step.
