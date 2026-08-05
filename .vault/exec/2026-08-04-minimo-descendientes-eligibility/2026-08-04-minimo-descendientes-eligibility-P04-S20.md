---
tags:
  - '#exec'
  - '#minimo-descendientes-eligibility'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:c2448ff5e5e67c5425842879c66a400f1d00af0bc8d63a5bf74e6f3857db09b1'
step_id: 'S20'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-plan]]"
---
# Route the canonical-record refusals reaching the descendiente add verb to the operator, because the verb catches only the answer-type error and the boundary projects the rest to a GENERIC translated refusal that discards the validator's own sentence, so the entry-date coherence rules this Phase shipped told the operator nothing about which field conflicted, and the discarded detail was written to the error log carrying the declared record

## Scope

- `src/cadrumo/entrypoints/cli/_config/_descendiente.py`

## Description

The Step's original premise was wrong, and correcting it was the first piece of
work rather than a footnote. The row said these refusals surfaced as raw
tracebacks. They did not. The error boundary carries a catch-all that projected
them into a generic translated refusal, which was measured directly by running
the projection over a real refusal rather than reasoning about it.

The row was corrected through the owning verb before the fix landed, so a reader
does not inherit the false premise from the structured surface.

Executed in this pass:

- Measure what an unhandled record refusal actually produced, and correct the
  row, the code comment and the test prose to say it.
- Catch the record's refusal family alongside the answer-type family the verb
  already handled.
- Render the validator's own sentence rather than the raw error, stripping the
  framework prefix so nothing structural reaches the operator.
- Add gates over all four catalogues, plus one that the pre-existing refusal
  family still translates.

## Outcome

The real defect is subtler than the row claimed and harder to have noticed. The
canonical record's validators write careful copy: they name the conflicting
field, the offending value, and both ways out. The verb caught only the
answer-type error, so every record-level refusal reached the operator as
"validation failed" in their own language, with that sentence discarded on the
way. An operator declaring a tutela guardian carrying an adoption anchor — the
case this Phase added the relación axis specifically to refuse — was told nothing
about which field conflicted. The copy existed and nobody had ever seen it.

That is worse to diagnose than a traceback would have been. A traceback is
obviously broken and gets reported. A translated generic refusal looks like the
system working, so the operator concludes their input was wrong in some way they
must guess at, and nothing about the surface suggests a defect.

The discarded detail was not silent either. The projection logged it, and the
error's input echo carries the record under construction: birth date, relación
and cohabitation in clear, with only the NIF redacted. Catching before the
boundary closes that too, and its absence is asserted rather than assumed.

Six gates cover it. The record-level refusal carries the field and the value in
all four catalogues; the record is not echoed back; and the answer-type family
that already worked still does, because widening a caught set is exactly the
change that quietly reroutes an existing refusal through the new arm.

## Notes

One gate caught a bug in itself before it caught anything in the product. The
language option belongs to the verb rather than the root, and placed at the root
the CLI refused it as unknown — so the test was asserting against the wrong
refusal. It failed loudly on that rather than passing on a coincidence, which is
the behaviour worth having and the reason the assertion names the expected field
rather than merely checking that something was refused.

The premise correction is the third time in this Phase that prose asserted
something the code did not do, and the first time the prose was mine. The row was
written from a one-line observation made while executing a different Step, and
carried into a Step row without being re-measured. An observation good enough to
open a row is not automatically good enough to be that row's stated reason.
