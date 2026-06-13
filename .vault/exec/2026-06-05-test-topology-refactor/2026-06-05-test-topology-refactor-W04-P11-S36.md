---
tags:
  - '#exec'
  - '#test-topology-refactor'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S36'
related:
  - '[[2026-06-05-test-topology-refactor-plan]]'
---

# `test-topology-refactor` `W04.P11.S36`

## Scope

Source tests.

## Description

- Removed duplicate campaign closeout aggregate tests that re-ran standing ratchets.
- Kept canonical ratchet tests in the central harness and behavior tests under owning packages.

## Outcome

Collection count dropped after deleting duplicate closeout aggregates and remained green.

## Notes

No data loss. Work was performed in a dirty shared workspace; unrelated concurrent edits were left intact.
