---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
step_id: 'S145'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P10.S145 Size Budget Inventory Repair

## Scope

Repair stale size-budget inventory entries exposed by residual decomposition and concurrent file movement.

## Description

- Removed obsolete legacy budgets for the now-shrunken modelo `_actions` module and moved `_actions` callables.
- Removed the obsolete profile censo `register` callable exception after the split.
- Made the tracked-file inventory ignore absent tracked paths so dirty renames do not produce a `FileNotFoundError`.

## Outcome

The size guard now measures existing tracked Python files and no longer fails on the deleted ledger switch test path or obsolete modelo/config callable exceptions.

## Notes

The guard still enforces line and callable budgets for existing files.
