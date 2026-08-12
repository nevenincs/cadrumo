---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-11'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:5061f20aa130c160c2968b69cb1efbd32077e74d0b745dec8b0306d1623a2cb9'
step_id: 'S133'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Report a missing rate tier as a missing classifier input, since a domestic operation lacking one refuses through the criteria model raising and the assembly reports the status and kind gaps while never naming the tier itself, so an operator sees an incomplete gap list and fixes one axis at a time. Pre-existing rather than introduced by the laziness work that surfaced it

## Scope

- `src/cadrumo/application/ledger`

## Description

- Drive the real assembly with a domestic operation carrying no tier, and read
  what it reports, before planning any change.
- Give the condition one home in the domain and have both layers ask it.
- Report the tier as its own gap, lazily, ahead of the axis probe.
- Mutation-prove the demand site from outside the checkout.

## Outcome

Delivered, and the defect is WORSE than the row recorded. The row said an
operator sees an incomplete gap list. Measured, the list was WRONG.

An ES-to-ES domestic operation with no readable rate tier reported
issuer_identification_state as its missing input. That is a fact the domestic
branch provably does not consume -- a sibling gate one package over asserts a
domestic operation reports needing only the establishment -- while the tier
that actually blocked it was never named at all.

The cause is a chain rather than a bad string, and it is worth recording
because each link is individually reasonable. The criteria model RAISES
without a domestic tier. The axis probe treats an unclassifiable criteria set
as "this branch might need everything", which is the right fail-safe when the
cause is unknown. And everything includes the identification. So a nameable,
known input became an anonymous failure and then re-surfaced wearing another
field's name.

What makes it a real operator harm rather than a cosmetic one: following the
instruction could not have unblocked them. Supplying a NIF-IVA changes nothing
the domestic branch reads. That is a refusal an operator cannot act on, which
is the one property every refusal in this module is contracted to have.

The condition now has ONE home. The predicate is exported from the IVA domain
and asked by both the model that enforces it and the producer that must
anticipate it. Restating it in the producer would have fixed this instance and
left the two free to drift -- which is the shape that produced the divergence
in the first place.

The demand is lazy, in the idiom the supply-nature demand already uses, with
union semantics over a still-open kind axis: an operation that MIGHT land on a
branch needing the tier is asked. Sparing an operation whose kind is merely
unread would send it straight back through the raise to the wrong field.

## Notes

Mutation-proven at the demand site by monkeypatching the predicate to never
fire, from outside the checkout so nothing under source changed: the blocker
case reds, the positive control and the cross-border laziness case both stay
green, and the restored tree is green again. The mutated run reds with a
validation error rather than an assertion, which is itself the confirmation --
that is the raise the gap exists to pre-empt.

TWO adjacent findings, neither this row to fix. First, a domestic operation
cannot settle its issuer identification at all, because Spain is absent from
the VAT identification prefix vocabulary; that is an open row of its own and
it is why the wrong gap was also an unanswerable one. Second, the peer churn
seen while verifying: an IVA category member was added without its member-set
fixture or component rows, reding nine domain tests, and a storage refusal
message became a locale key while its test still matched the prose. Both are
outside this surface and are left to their owners.
