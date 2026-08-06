---
tags:
  - '#exec'
  - '#test-topology-refactor'
date: '2026-06-05'
modified: '2026-07-17'
body_hash: 'sha256:6397518e645085cc0ca83a64c149014e9cfcc3205e8628180153478c96cad0ee'
step_id: 'S15'
related:
  - '[[2026-06-05-test-topology-refactor-plan]]'
---

# `test-topology-refactor` `W02.P05.S15`

## Scope

Source tree imports.

## Description

- Collected relocated source tests successfully under `src/aeat`.
- Confirmed relative imports introduced by `tests` directory insertion resolve during pytest collection.

## Outcome

`uv run --no-sync pytest --collect-only -q src/aeat` succeeded.

## Notes

No data loss. Work was performed in a dirty shared workspace; unrelated concurrent edits were left intact.
