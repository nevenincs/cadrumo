---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:0b6777d9692e0d1d79b12dd9e059ab04b668ee7e815b112ab46c29655b9e9e2f'
step_id: 'S23'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# Retype extract_csv_from_url's return annotation from bare str to AeatCsv, resolving this row's OBSOLETE AS WRITTEN state on measurement rather than deleting it. The row assumed the sibling justificante-identity-matching plan would hand off a new persisted cotejo-derived CSV field. It did not. Its chosen Option 4 recovers the CSV non-persistingly from FiledDeclaracionArtefact.source_url through extract_csv_from_url, so there is no new field, but there is a real successor target. That function already shape-validates its result with is_aeat_csv, the exact canonical contract AeatCsv carries, so the retype documents an invariant the function already enforces rather than adding a constraint. Confirm all four consumers still type-check

## Scope

- `src/cadrumo/adapters/outbound/aeat/sede/_declarations_remote.py`

## Description

- Retype `extract_csv_from_url`'s return annotation from bare `str` to the
  canonical alias.
- Import the alias from the core identity facade.
- Extend the function docstring to state what the annotation does and does not
  do, so a reader does not mistake it for a runtime guard.

## Outcome

The single changed declaration is in
`src/cadrumo/adapters/outbound/aeat/sede/_declarations_remote.py`.

The two contracts were read against each other before claiming equivalence, and
they agree on the shape but not on acceptance. The shape predicate this
function already applies is an anchored full match on eight to thirty-two
uppercase alphanumerics; the alias constrains to the same minimum, maximum and
pattern. The alias additionally normalises by stripping and uppercasing before
its constraints run, so as a validating boundary it ACCEPTS and corrects a
lowercase or padded value that the predicate refuses outright.

That divergence does not affect this row, and the reason is worth stating: the
values this function returns have already passed the predicate, so they are
exactly the fixed points of the alias's normaliser and satisfy its constraints
unchanged. The annotation is therefore truthful documentation of an invariant
the guard enforces, and it neither widens nor narrows anything. The docstring
now says so explicitly, because the alias is a pydantic annotated type and a
reader could otherwise assume a plain function's return annotation validates.

Consumers were counted rather than assumed. There are four production call
sites, matching the row's claim: the sede parse helper, the declarations fetch
path, the declarations walker, and the filed-observation persistence path in
the live application layer. A fifth reference is the package facade's
re-export, which is not a call. All four consume the result as a plain string,
either interpolating it into a URL or passing it to a model field already typed
on the alias, and the alias is a string annotation to the type checker, so
every consumer type-checks unchanged.

## Notes

Nothing was left bare in this row's file.

The sede declarations suite has one failure unrelated to this change: a
submitted-file context test fails resolving an export layout for a modelo whose
registry revision reports no exports. That is registry work another campaign is
mid-flight on; the test exercises no CSV path and fails identically without
this change.

Observed but out of this row's scope: the filed-observation persistence
consumer compares this function's result against a receipt CSV using inline
strip-and-uppercase. Both sides are already canonical after this retype, so the
local normalisation there is redundant rather than wrong.
