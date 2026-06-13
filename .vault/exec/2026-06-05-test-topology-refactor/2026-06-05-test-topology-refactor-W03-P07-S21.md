---
tags:
  - '#exec'
  - '#test-topology-refactor'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S21'
related:
  - '[[2026-06-05-test-topology-refactor-plan]]'
---

# `test-topology-refactor` `W03.P07.S21`

## Scope

Pytest marker registry.

## Description

- Confirmed marker registry contains `unit`, `integration`, `aeat_live`, and the accepted `hex_*` markers.
- Removed the old marker vocabulary from the configured pytest registry.

## Outcome

Marker registry integrity test passed.

## Notes

No data loss. Work was performed in a dirty shared workspace; unrelated concurrent edits were left intact.
