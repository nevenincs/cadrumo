---
tags:
  - '#exec'
  - '#minimo-descendientes-eligibility'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:8dbd105f83482330e9cc6b31c8bf0828cd7881c125c1a430d36b25f8b7ac8032'
step_id: 'S16'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-plan]]"
---
# Model month-level guarderia spend as an optional sparse per-month map alongside the annual figure, refusing both at once for one child

## Scope

- `src/cadrumo/domain/contribuyente/family.py`

## Description

The heading and scope above are machine-filled from the Step row as it stood when
this record was scaffolded, so they preserve the pre-correction text: a BLOCKED
clause naming a per-comunidad regional table, and one scoped file. The row itself
was corrected before it was checked and now names neither. Read the heading as a
record of what the row said, not as a live instruction.

That clause was already dissolved before this work began.
The governing decision record established that the window's upper bound is the
childcare centre's legal obligation, not this application's: the centre files the
informative return reporting childcare custody, applies its own region's
schooling calendar, and reports the eligible months to the authority directly.
Building a per-comunidad table would compute a determination the law assigns to a
party holding a calendar this application does not, and would risk contradicting
the return the authority already holds. The regional table is retired as a
precondition and must not be built.

The Step landed in two commits. The first shipped the persisted shape and the
engine rules and declared itself incomplete by design: nothing could write the
new field, so no profile changed behaviour and the row stayed open. This record
covers the second, which makes the field writable and makes it arrive.

Executed in this pass:

- Author one shared grammar for the month map, consumed by the flag door, the
  fact index and the wizard page alike.
- Add the monthly-spend fact path, its emitter, its reader and its regex branch,
  ordered ahead of the annual path so the longer key cannot be swallowed by the
  shorter alternation.
- Add the monthly flag key, its parse, and its entry in both advertised help
  strings across all four catalogues.
- Add one flat wizard page carrying the whole map, with a grammar answer
  validator and a flow-scope one-spend-authority-per-child verdict.
- Mint four locale keys with real translations in all four catalogues.
- Carry the map on the JSON payload as typed month rows and mirror both canonical
  refusals there.
- Declare the field on the user-profile schema.
- Delegate the derived-facts injector to the canonical record, closing a second
  aggregation path found during the work.
- Wire the previously dead shape advisory into the calculate path.
- Add grammar, round-trip, anti-tautology, wizard-walk, resolver and end-to-end
  CLI coverage.

## Outcome

An operator can now declare month-level guarderia spend through either door and
see it reach the Art. 81.2 increase. The end-to-end proof drives the real CLI:
declare a child turning three in April with spend across January to July,
calculate, and the casilla resolves to the three post-birthday months rather than
zero.

The grammar separates entries on a semicolon because the comma already separates
the flag's own keys, and admits an inclusive month range because the dominant
real shape is a constant fee across an enrolment span. Ranges are input only; the
stored fact is always the expanded month-sorted form, so a map entered two ways
produces one set of stored bytes and the resume round-trip cannot drift on how
the operator happened to type it.

The wizard page is flat and carries the whole map on one answer. A per-month
sub-question inside the per-descendant group is a nested repetition the substrate
has no primitive for, so the grammar validator carries the structure the widget
cannot. That constraint was measured rather than assumed.

The one-authority-per-child rule is mirrored at three boundaries: the canonical
record, the JSON transport, and a flow-scope wizard verdict, with the flag door
raising its own translated refusal rather than letting a pydantic error surface
untranslated. Landing one half of an incompatibility pair is this campaign's most
repeated defect, so all halves ship together.

The discovery that changed the shape of the work: the derived-facts injector
carried its own loop summing the annual spend fact under an inline age test, so
it never read the canonical record and had already diverged from it. Without
fixing that, this entry surface would have been strictly worse than the gap it
closes, because a taxpayer following the new advisory would have moved their
figure onto the monthly map and received nothing. Replaying the previous
algorithm in process, with no source mutated, measured the divergence directly: a
monthly-only child yielded zero spend where the record holds seven hundred and
twenty euros, a turning-three child yielded a zero cap population, and the annual
path was unchanged. The injector now delegates to the canonical record, which the
one-aggregation-path discipline required independently.

The cap population moved with it, necessarily. A turning-three child contributes
euros but is not menor de tres al devengo, so leaving the narrower count would
have capped them at zero and handed the under-grant straight back.

An annual-only figure in the turning-three period still contributes nothing,
because it spans the birthday and cannot be apportioned. That zero is correct;
silence about it would not be. The advisory names the child and the key, and
points at the certificate the taxpayer already holds, because the eligible months
genuinely are the ones the centre determined and reported.

Verification: 2614 tests pass across the domain, wizard, modelo, descendiente CLI
and locale surfaces. Locale parity, translation honesty, JSON schema conformance,
documented command conformance, import hygiene and the API stub gate are green.
Every new token has test coverage in every production site that carries it.

## Notes

The heading of this record carried the phrase "BLOCKED on a per-comunidad regional table for when the second infant-education cycle may begin" long after that blocker was retired. It is corrected here.

The blocker was dissolved by research rather than satisfied: the informative return reporting childcare custody is filed exclusively by the centre, which is required to apply its own region's calendar and report the resulting months to the authority. The determination was therefore never this application's to make, and building the table would have risked contradicting a return the authority already holds. The plan's own Parallelization section records this and warns in terms that the blocker must not be reinstated from reading the row.

That warning is why this correction matters more than tidiness. The plan row was updated when the blocker retired; this record was not, so the record became the surviving carrier of exactly the stale premise the plan warns readers against. A reader who trusts records over prose — which is the ordinary reader, because the record is the structured surface — would have reinstated a precondition the campaign had already measured out of existence.

The same drift is corrected in the plan's own prose in the same change: a sentence there still said this Step was awaiting review "which is why the row is still open", while the row had been checked.

Surfaced by the campaign-close honesty review, which was looking for exactly this class — a document that outlives the correction that retired its premise.

