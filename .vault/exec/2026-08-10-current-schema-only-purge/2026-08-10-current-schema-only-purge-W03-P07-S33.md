---
tags:
  - '#exec'
  - '#current-schema-only-purge'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:08db4fbe8434036308c4e4413d4fc935eee8a83802f5468990eb94d44374d3df'
step_id: 'S33'
related:
  - "[[2026-08-10-current-schema-only-purge-plan]]"
---

# Establish which onboarding paths set the profile activity-start date

## Scope

- Read-only. No production file changed.

## Description

- Census the writers of the activity-start fact rather than the readers.
- Read the fact's own schema declaration.
- Test whether the censo reconciliation supplies it.
- Answer the disconfirming clause about post-hoc edits.

## Outcome

Answered, read-only, no code changed.

The fact is declared OPTIONAL in the user-profile schema and is asked as an
optional wizard question in the profile section. So a completed onboarding can
produce a profile without it, and no path forces it. That half of the row is
settled: absence is ordinary, not exceptional.

The more consequential half was not the question asked. The censo
reconciliation does NOT write this fact, despite the fact key sitting in the
censo namespace, and the shipped operator-facing text says so in four locales,
describing the value as operator-declared and not yet contrasted with the
authority. The wizard is the sole production writer.

Absence is already fail-closed and needs nothing: the first-period predicate
returns false when the date is missing, so the gate blocks rather than proving a
zero. The exposure is the DECLARED case, not the undeclared one -- a proven
first-period zero on the compensacion can rest on a date the taxpayer typed and
nothing has checked. That is rowed separately rather than decided here, because
it is a policy question about how much weight a self-declared uncontrasted fact
may carry, not a defect with an obvious remedy.

## Notes

The row was written to answer a frequency question that had been asked, refused
as unanswerable from code, and then narrowed to the part code can answer. The
narrowing held: the code answers which paths write the fact and whether it can
be absent, and says nothing about how many real profiles carry it. That number
remains a question about taxpayer data.

One limit of this pass, stated rather than implied: the disconfirming clause
asked whether the fact can be set after the fact by an ordinary edit, which
would make an onboarding-path enumeration the wrong instrument. No generic
profile fact-set path was found, so the enumeration stands. Whether re-running
the wizard over an existing profile amounts to the same thing was not
established, and a reader who needs that answer should not take its absence here
for a negative.
