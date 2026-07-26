---
tags:
  - '#exec'
  - '#evidence-revision-identity'
date: '2026-07-26'
modified: '2026-07-26'
step_id: 'S08'
related:
  - "[[2026-07-25-evidence-revision-identity-plan]]"
  - "[[2026-07-26-evidence-revision-identity-adr]]"
---

# RESOLVED BY S10, the evidence gap does not enter revision identity, it is prevented at verify instead so no identity carrier is needed

## Scope

- `see 2026-07-26-evidence-revision-identity-adr`

## Description

This record is written after the fact to close a
`plan-closure-requires-exec-records` gap. The step closed without a source change
and this record states why, rather than manufacturing activity that did not
happen.

## Outcome

**Closed without source change. The mechanism this step proposed was examined,
measured and then rejected on its merits, not dropped for cost.**

The step carried the cheaper mechanism found when the supersede transition
collapsed: record the deductible-evidence gap as a `source_issue` at calculate, so
a post-attach recalculation derives a different id naturally. That route was
genuinely attractive. `source_issues` is already an argument to the revision id
deriver, already threaded at the persist site, and its documented purpose is
precisely that distinct resolution outcomes cannot collapse to one revision — an
axis purpose-built for the shape this needed, requiring no new verb and no change
to what identity means.

It was rejected on what it leaves in the store. Routing the gap through identity
means verify still grants: a revision reaches `VERIFICADO_COMPLETO` carrying a
frozen bundle that asserts a deduction the taxpayer has no right to exercise, and
the new id mints a SECOND revision beside it as the recovery. It makes the bad
state recoverable where the promotion makes it unreachable.

The cost argument is explicitly not why it lost, and that is worth recording
because it is the reading a later reader will assume. A prior pass measured the
blast radius of moving revision identity as near zero — four production deriver
call sites and no pinned revision-id literals in tests — so the usual reason to
prefer a cheaper fix had evaporated. The identity route is also conceded to be
the more faithful model of the domain. It still lost, because prevention beats
recovery on a filing-grade path.

The two options were never competing fixes for one defect. Without the promotion,
verify keeps granting revisions asserting unexercisable deductions and the
identity route makes them recoverable while leaving the cause untouched. With the
promotion, the identity route has nothing left to do here. That asymmetry decided
it.

Content-addressing is left doing the job it was designed for. Where evidence is
value-affecting it already moves the id through the outputs it changes — the
renta first-slice pipeline reclassifies an INCOMING row carrying purchase
evidence as a refund, which moves the aggregation, the casilla values and
therefore the id. An evidence term in the deriver would double-count that case
and do independent work only where, by construction, no calculation differs.

## Notes

One boundary on this closure is stated in the governing decision and is repeated
here because it is what would reopen the question: the finding class beyond
deductible IVA was not exhaustively enumerated. A gap class NOT detectable at
verify from the live ledger would defeat the prevention argument and put identity
back on the table. This one is detectable — verify already computes the exact
predicate — so the argument holds for the case at hand and is not claimed to
generalise.

The plan row for this step is checked and was not touched by this record.

Semantic search was unusable throughout the campaign: the code index reports
roughly 68 sections against about 4,546 files while self-reporting healthy, and
searches timed out at 120 and 300 seconds against a service whose latest indexing
job had failed. The `source_issues` axis cited above was found by exhaustive
signature sweep rather than by search.
