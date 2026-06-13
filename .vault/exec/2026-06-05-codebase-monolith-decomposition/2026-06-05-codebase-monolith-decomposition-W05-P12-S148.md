---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S148'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W05.P12.S148 Declaracion Parser Test Split

## Scope

Split the current declaracion parser synthetic-fixture regression group into a focused test module.

## Description

- Moved late synthetic fixture parser tests into `test_parser_synthetic_fixtures.py`.
- Kept earlier parser boundary tests and shared PDF helpers in `test_parser_boundary.py`.
- Added the required unit and inbound-adapter pytest markers to the new test module.

## Outcome

`test_parser_boundary.py` is now below its current size budget, and the new synthetic fixture module is below the default module threshold.

## Notes

The split preserves parser calls against real fixture files.
