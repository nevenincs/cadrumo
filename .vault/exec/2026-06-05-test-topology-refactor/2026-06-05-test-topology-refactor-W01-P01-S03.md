---
tags:
  - '#exec'
  - '#test-topology-refactor'
date: '2026-06-05'
modified: '2026-07-17'
body_hash: 'sha256:d64cc695e2b2894c131e67eca11a4dcca531c03740de921ae1561c411f21a073'
step_id: 'S03'
related:
  - '[[2026-06-05-test-topology-refactor-plan]]'
---

# `test-topology-refactor` `W01.P01.S03`

## Scope

Pytest discovery and marker registry baseline.

## Description

- Read the current pytest discovery configuration in `pyproject.toml`.
- Read the marker registry location in `pyproject.toml`.
- Confirmed the refactor starts from a discovery pattern that still accepts underscore-prefixed test modules.

## Outcome

- Current `python_files` is `["test_*.py", "_test_*.py"]`.
- Current marker registry starts at the `markers` array in `pyproject.toml`.
- The accepted target is `python_files = ["test_*.py"]` after underscore-prefixed files are renamed.

## Notes

- No marker rewrite was performed in this baseline step.
