---
tags:
  - '#exec'
  - '#period-grammar-standardisation'
date: '2026-06-11'
modified: '2026-06-11'
step_id: 'S28'
related:
  - '[[2026-06-11-period-grammar-standardisation-plan]]'
---

# W02.P11.S28 Period Parser Cleanup

Scope: `src/aeat/domain/period.py`.

## Description

- Delete the obsolete combined-input parser regexes after downstream producers migrated to `aeat.core.Period`.
- Preserve the live AEAT declaration boundary that receives a bare quarterly token paired with `ejercicio`.
- Update tests around the remaining adapter and refusal behavior.

## Outcome

The domain period helper surface now reflects typed `aeat.core.Period` as backend authority and no longer parses combined calendar strings.

## Notes

`W01.P05.S17` remains open because it also names source docstrings outside this domain slice. The overview calendar files currently contain non-authored WIP, so their stale docstrings were not edited in this commit.
