---
tags:
  - '#exec'
  - '#minimo-descendientes-eligibility'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:59c1cd6c7809ed738009f7cf74f1182f1287cdaf8ef4534f1f896e973ebbed23'
step_id: 'S41'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-plan]]"
---

# Bound the interpolated descendant list in both maternidad advisories

## Scope

- `src/cadrumo/application/modelo/_calculate_input.py`

## Description

- Bound the per-descendant list interpolated into both maternidad advisories, sharing the constant with the sibling module rather than restating it.
- Test at descendant counts above the observed crossing points rather than at a single index.

## Outcome

Both advisories are now bounded independently of household size. Measured by construction across sizes rather than by reading: 475 characters at one descendant, 494 at two hundred.

Before the fix, message length grew one entry per descendant against a fixed cap, so past a threshold the model refused and **a non-blocking advisory became a hard validation error that stopped the filing** — at exactly the moment it had something to say. The crossing points were thirteen declared descendants for the withheld advisory and twenty-five for the ambiguous-relación one, both surfacing a raw validation error to the operator. An independent mutation probe restoring the unbounded join confirmed both figures rather than accepting them.

The tests carry an anti-tautology control: a case reconstructing what the unbounded join of the same ids would have cost, asserting it exceeds the cap. Without it the suite proves the messages are short, not that the bound is what keeps them short. Two further tests assert the bound stays actionable — it still names three indices and says how many more — since a household of sixty reading as a household of three would be a different defect in the same message.

## Notes

This was the earlier cotizaciones crash one layer down. That fix corrected the message's STATIC length; neither the implementing agent nor the coordinator constructed either advisory at more than one index, so the DYNAMIC term survived a fix aimed at the same cap. Verifying the decision is not verifying the output, and the output here was a function of household size.

The bound shares its constant with the sibling advisory module that first hit this, rather than restating the number, so the two cannot drift apart. The rendering differs — bare ids in one, fact paths in the other — but the judgement being made is one judgement.

The work was complete and uncommitted when its author's weekly limit stranded it: source staged, tests written, only the commit missing. Landed by the coordinator with the author's reasoning kept verbatim rather than rewritten.

A later full enumeration of every diagnostic site showed this fix to be **necessary and not sufficient for the class**. It sits at 493 of 512 — correct to five thousand descendants and nineteen characters from re-crashing on one added clause — and the real defect turned out to be fixed prose measured against nothing rather than unbounded lists. Two further advisories were found that could not be constructed at all.
