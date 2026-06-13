---
tags:
  - '#exec'
  - '#test-topology-refactor'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S04'
related:
  - '[[2026-06-05-test-topology-refactor-plan]]'
---

# `test-topology-refactor` `W01.P02.S04`

## Scope

Package-root integrity tests.

## Description

- Moved naked package-root test modules into the central package test harness.
- Preserved filenames for already valid `test_*.py` modules.

## Outcome

- Package-root tests now live under `src/aeat/tests`.

## Notes

- No pytest execution was run during this mechanical relocation step.
