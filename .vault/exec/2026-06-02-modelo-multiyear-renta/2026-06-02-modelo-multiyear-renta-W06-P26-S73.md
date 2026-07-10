---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-06'
step_id: 'S73'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# build the Beckham flat-rate impatriate engine per A5-151 (Ley 35/2006 art.93) (vaultspec-high-executor)

## Scope

- `src/aeat/domain/calculations/engines/_modelo_151.py`

## Description

- Rebaseline the M151 Beckham calculation surface with RAG and targeted tests.
- Confirm the live registry computes the art. 93 flat-rate cuota through the current M151 calculation path.
- Close the stale-open engine row without changing source code.

## Outcome

Closed as current-code satisfied. The live M151 enrollment test drives real calculations for two in-window renta years and asserts the BOE-scale worked examples.

## Notes

Verification: the focused W06/W07 stale-open test batch returned 42 passed.
