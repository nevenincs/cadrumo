---
tags:
  - '#exec'
  - '#minimo-descendientes-eligibility'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:15a7b301fa6a796ec1d36a31960631869514421ae78687f3c56eb9ae4e33736b'
step_id: 'S35'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-plan]]"
---

# Close the 0611 registry-computed question as a measured non-defect

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/100/revisions/2024/formulas/`

## Description

- Research the routes by which casilla 0611 could become registry-computed.
- Test the parity premise the row rested on rather than inheriting it.
- Close the row as a non-defect, with the reopening condition recorded.

## Outcome

No code changed, and that is the finding rather than an absence of one.

The row asked for 0611 to become registry-computed like its sibling. Research retired that premise: the sibling's formula is a flat rate times a scalar count, minned against two other scalars, so every eligible child contributes the identical amount and its cap never varies per child. Casilla 0611, after the post-birth alta increment landed, has a cap that varies with WHICH child carries that increment. The sibling never had to solve this casilla's problem, so parity was never achievable.

That reframes the original complaint entirely. Two different rule shapes carried by two different mechanisms is what correct modelling looks like; fragmentation is two mechanisms for the SAME shape, which is what this campaign removed elsewhere. The asymmetry was flagged in good faith by the agent who later retired it.

The arithmetic is also not expressible with today's primitives, measured rather than assumed: the closed aggregation-op set passes raw per-row fields through without arithmetic, and the formula ops are fixed-arity over statically declared argument lists. Nothing iterates a variable-length row set applying a per-row conditional cap.

## Notes

The decisive finding was a tension the research was not asked to resolve, and it reversed the answer. A profile-sourced resolver projecting per-child rows would need no entry-surface change at all, because the descendant facts already have the exact indexed sub-record shape a live atribucion-member resolver reads. But if each synthesised row carries an already-capped euro amount computed outside the registry, folding those rows inside it is cosmetically registry-computed while the cap-selection rule sits one layer FURTHER from view than it does today. That is the same objection that barred the single-copy route, recurring per row instead of collapsed to one scalar. A fix that makes a gap harder to see is worse than the honest gap. Without that paragraph the resolver route would have been taken.

The only genuine route is a new aggregation primitive reading two selector fields per row and applying a conditional cap before summing. That is a schema and engine extension whose entire value is auditability: the figure this casilla produces today is correct, and no taxpayer receives a different number either way.

This is recorded as a CLOSURE, not a deferral, and the distinction is load-bearing. A campaign must not narrow its own completion criterion, and this has exactly that shape. It is not the work being judged too expensive -- it is the criterion being measured false. If a future reform makes this casilla's cap uniform again, the parity question genuinely reopens and this decision should be revisited rather than cited as settled.

The research was commissioned as findings rather than a recommendation, which is why the sibling-parity premise was tested at all instead of arriving already resting on it.
