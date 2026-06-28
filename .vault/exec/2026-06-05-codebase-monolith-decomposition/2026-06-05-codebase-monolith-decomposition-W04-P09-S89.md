---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S89'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W04.P09.S89 Core Adapter Error Registry Shards

Scope: decompose the core error registry adapters module behind the core errors facade.

## Description

- Split adapter error-code declarations into `_adapters_part1.py` and `_adapters_part2.py`.
- Kept `_adapters.py` as the aggregate module exposing `_DECLARED_ERROR_CODES`.
- Preserved adapter error-code declaration order and payloads.
- Verified shard module sizes remain below the hard module-size budget.

## Outcome

The adapter error registry is decomposed behind the existing core errors facade without changing public registry imports.

## Notes

Ruff passed for the adapter registry aggregate and shards. `_adapters.py` is 16 lines, `_adapters_part1.py` is 668 lines, and `_adapters_part2.py` is 633 lines.
