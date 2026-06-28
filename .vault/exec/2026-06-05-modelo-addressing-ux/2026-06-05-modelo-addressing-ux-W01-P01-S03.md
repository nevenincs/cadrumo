---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S03'
related:
  - '[[2026-06-05-modelo-addressing-ux-plan]]'
---

# W01.P01.S03 - continuous decomposition baseline

Scope: persist the continuous decomposition baseline and extraction order.

## Description

- Record `_modelo.py` as the current decomposition baseline.
- Record the ordered extraction sequence for the continuous plan.
- Preserve known residual risks from the prior code review as first-wave guardrail work.
- Anchor resume implementation behind lifecycle and calculation extraction.

## Outcome

The baseline is `_modelo.py` at 4248 lines, with remaining command bodies and helper seams in the legacy root. The extraction order is:

- W01: baseline, semantic discovery, ADR gate, and guardrails.
- W02: modelo lifecycle and discovery command surfaces.
- W03: work calculation command surface.
- W04: work resume natural-key plus legacy exact-id support.
- W05: recurring verification, final review, and residual risk closure.

This order keeps the user's requested sequence intact: modelo first, calculation second, resume last.

## Notes

The baseline intentionally treats exact UUID or exact work identifier resume as legacy compatibility, not as the common operator path.
