---
tags:
  - '#exec'
  - '#test-topology-refactor'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S22'
related:
  - '[[2026-06-05-test-topology-refactor-plan]]'
---

# `test-topology-refactor` `W03.P07.S22`

## Scope

Marker registry.

## Description

- Removed direct legacy marker names from durable docs and registry surfaces.
- Kept integrity enforcement for retired marker names without reintroducing them as active vocabulary.

## Outcome

Retired marker scan on configured surfaces is clean except product path names.

## Notes

No data loss. Work was performed in a dirty shared workspace; unrelated concurrent edits were left intact.
