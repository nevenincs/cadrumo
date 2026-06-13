---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S08'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
---

# `repo-health-triage` `W01.P02.S08`

Scope: `.importlinter`.

## Description

- Added narrow import-linter exceptions for current real-behavior
  `aeat.tests.secure_sql` test-helper consumers.
- Preserved production layer contracts by avoiding broad application or domain
  wildcards for test-helper imports.
- Verified `just audit-structure` after the policy update.

## Outcome

`lint-imports` now reports four kept contracts and zero broken contracts.

## Notes

The command still reports unrelated stale-ignore warnings already present in the
configuration.
