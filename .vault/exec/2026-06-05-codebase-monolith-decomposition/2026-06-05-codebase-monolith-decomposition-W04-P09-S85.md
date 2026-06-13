---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S85'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W04.P09.S85 Core Domain Error Registry Shards

Scope: decompose the core domain error registry module behind the core errors facade.

## Description

- Split the ordered domain error-code declarations into `_domain_part1.py`, `_domain_part2.py`, and `_domain_part3.py`.
- Keep `_domain.py` as the aggregate module exposing `_DECLARED_ERROR_CODES`.
- Preserve every registered error-class qualname and `ErrorCode` payload unchanged.

## Outcome

The domain registry declarations now sit below the hard module-size budget while `aeat.core.errors.registry` continues to aggregate through the same symbol.

## Notes

No error classes moved, and no public consumer import path changed.
