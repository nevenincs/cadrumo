---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S87'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W04.P09.S87 Core Application Error Registry Shards

Scope: decompose the core error registry application module behind the core errors facade.

## Description

- Verified the existing application registry split into `_application_part1.py` and `_application_part2.py`.
- Kept `_application.py` as the aggregate module exposing `_DECLARED_ERROR_CODES`.
- Confirmed the application shard modules remain below the hard module-size budget.
- Preserved the registry facade import path through `aeat.core.errors.registry`.

## Outcome

The application error-code registry is decomposed behind the existing core errors facade without changing the registry aggregate contract.

## Notes

Ruff passed for the application registry aggregate and shard files. `_application.py` is 16 lines, `_application_part1.py` is 891 lines, and `_application_part2.py` is 534 lines.
