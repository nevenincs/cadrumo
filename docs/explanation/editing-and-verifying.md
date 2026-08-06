# Editing and verifying a calculation

This page covers the two ideas at the heart of the tool: what a saved
calculation actually is, and what the completeness check does - and does not -
tell you. It is written for everyday taxpayers working through a
{term}`modelo`; for the step-by-step actions it links out to the how-to
guides.

## A calculation is a saved version, not a final answer

Each time you run a calculation, the tool saves that result as its own
version and keeps the ones that came before. Nothing is overwritten. Tax work
is rarely right the first time: you enter a figure, calculate, spot something
off, correct it, and calculate again - and every attempt stays on disk,
identified by its exact contents, so you can compare versions and go back. A
saved version is a record of one attempt, not a verdict; its numbers commit
to nothing until you decide they do. The mechanics live in
[The filing workflow](../how-to/filing-spine.md).

A modelo is made of casillas (numbered boxes). Each box either holds a value
or waits for one. Editing is the act of giving a box the value the form still
needs, then recalculating so the totals reflect it - see
[Review and supply calculation inputs](../how-to/review-calculation-values.md).

## What verifying checks

Verifying runs a completeness check over a draft against the agency's
published rules for that modelo and year: every required box has a value,
the sums add up with no box contradicting another, and nothing blocks the
form - including conditions outside the draft itself, such as an earlier
period this form builds on being filed and evidenced. The check saves a
report whatever the result, and the draft lands in one of three states:
**complete** (verified and locked), **incomplete** (required boxes still
empty), or **blocked** (a failed rule or an unresolved dependency, named in
the report). Running the check and acting on each finding is covered in
[Verify a draft filing](../how-to/verification-reports.md).

A passed check is a local check: it means "my draft is complete and
consistent", never "AEAT accepted my filing", "the upload will succeed", or
"I am on time" - the tool never contacts AEAT, and the check ignores
deadlines entirely.

## Why the tool wants a verified version before it builds the upload file

The upload file is the thing that leaves the tool and goes to the agency, so
it is built only from a version that has passed the completeness check (or
one already recorded as filed). The tool refuses a plain draft. The check is
the gate a version has to clear before it can become a filing - protection
against an incomplete draft being filed by accident.

## Where this sits in the journey

This page is part of the [how-it-works overview](index.md)
cluster. Earlier filings feed into later ones; for how a verified prior
period carries forward, see
[How filings build on earlier ones](building-on-earlier-filings.md). Once a
version has passed the check, the next outputs are covered in
[Reviewing your numbers and producing the upload file](reviewing-and-exporting.md).
