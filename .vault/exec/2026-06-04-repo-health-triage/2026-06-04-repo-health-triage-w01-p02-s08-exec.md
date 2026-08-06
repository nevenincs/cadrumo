---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-07-17'
body_hash: 'sha256:4a96f4c298b3da3a0f10056f1d27c8ebdaf0a9180e877ba4e0ca36282529b654'
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
