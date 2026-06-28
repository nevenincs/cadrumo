---
tags:
  - '#exec'
  - '#cli-operator-surface'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S46'
related:
  - '[[2026-06-10-cli-operator-surface-plan]]'
---

# W04.P09.S46 M036 CLI Read-Back Verbs

Scope: verify `aeat app modelo m036 list` and `view` are mounted.

## Description

- Verified live help lists `m036 list` and `m036 view`.
- Ran CLI command-shape tests for the M036 surface.
- Ran documented-command conformance.

## Outcome

S46 is closed. The M036 read-back verbs are available on the CLI and covered by gates.

## Notes

- Checks run: `pytest src/aeat/entrypoints/cli/tests/test_m036_command_shape.py`.
