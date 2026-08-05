---
tags:
  - '#exec'
  - '#minimo-descendientes-eligibility'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:a44907d1eace1e735cf34a49a91e87ce017a9c9c6abe3c73fe23d8ead7b1f60c'
step_id: 'S48'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-plan]]"
---

# Stop the calculate boundary projecting an internal ValidationError to the generic CLI-validation refusal, because the operator is told to check arguments that are correct while the real cause reaches only the error log, which is the same defect S20 fixed for the descendiente add verb still live on calculate

## Scope

- `src/cadrumo/entrypoints/cli/`
- `src/cadrumo/application/modelo/_calculate_input.py`

## Description

- Reproduce the defect through the real CLI before changing anything.
- Bound the operator-supplied actor label at the CLI boundary, naming the option
  and the accepted length, in all four locale catalogues.
- Classify a fault raised below argument handling as an internal record fault
  rather than an argument refusal, on both the direct calculate verb and the
  wizard.
- Carry the failing record and its violated fields on the error context.
- Cover both directions with real inputs driven through the real CLI.

## Outcome

Commit `9df4aa1e67`.

The Step named the calculate verb. The catch site is not there: `ValidationError`
is one arm of the tree-wide projection table in the CLI error boundary, walked
for every command. Nothing in the calculate module caught it, which is why the
Step's second named path, the calculate input bundle, turned out not to be the
site either -- that function already narrows, because a pydantic
`ValidationError` is a `ValueError` and its `except ValueError` arm converts one
into a specific refusal carrying the real message.

## The discriminator, and what it replaced

Faults are classified by the REGION of the callback they were raised in, not by
inspecting the exception. Below the point where the work unit is resolved, the
input bundle is built, and the actor label is bounded, every value is
application state by construction, so a `ValidationError` from there is a record
the application built and refused.

Two alternatives were reached for and rejected on measurement rather than taste.

Reading the error's `loc` or model title to decide whether a CLI parameter is
named requires a map of parameter names kept in step with every internal field
rename, and agrees with the truth only until the first collision between a CLI
option name and an internal field name. The region boundary cannot drift out of
step with itself.

Removing the `ValidationError` arm from the projection table outright is the
cleanest narrowing available and would have been the right answer if the arm
were dead. It is not: a live test drives `ledger add --date not-a-date` and
depends on that arm to produce the argument-time refusal. Removing it would
reclassify a genuine argument fault as an internal defect on every verb in the
tree, which is both a real regression and far outside this Step.

## The vocabulary already existed

`CliOutboundPayloadBoundaryError` was already declared, already registered
against an INTERNAL error code, and already localised in four catalogues, with a
docstring naming this exact defect -- an operator told "the command input failed
validation, check the command's arguments" about arguments that were entirely
correct. It had no raise site anywhere in production. The Step wired it up rather
than adding a fourth boundary family.

Its context was empty, so the refusal said a defect had occurred without saying
which contract broke. It now carries the failing model's name and, per violation,
the field path and the constraint message. It deliberately does not carry the
pydantic `input`: the value that breached a constraint on this path is taxpayer
data, and it is exactly the value that must not cross an output boundary. A test
asserts the offending value is absent from the rendered context.

## The reproductions, both real

The argument direction is an actor label one character over the bucket event's
bound. Before, it ran the whole calculation and then refused with the generic
text and a null context. After, it refuses at parse time naming the option, the
accepted length, and the length received. A companion test drives a label exactly
AT the bound and asserts it calculates, so a guard that refused every label
cannot pass as one that refuses only over-long ones.

The internal direction needed a fault with no operator value in it at all. The
default audit actor is resolved from the active profile label. `ProfileName`
permits 128 characters and the bucket event's actor permits 64, so renaming a
profile to a legal long label -- through the real rename verb, which accepts it
without complaint -- makes calculate refuse on a command line carrying nothing to
correct. That is a live defect, not a simulation, and it is the proof the Step
needed.

## Notes

The internal reproduction is a real defect WIDER than this Step. A profile label
between 65 and 128 characters is legal everywhere the profile surface touches it
and breaks every verb that records an audit event under it: the same refusal was
observed on `work create`, before calculate was even reached. This Step makes
that failure honest rather than misdirected; it does not repair it. Choosing
between widening the persisted actor contract and deriving a label that fits is a
durability decision with consequences for stored events, and it belongs to a row
of its own rather than to a boundary-attribution Step. Reported to the axis lead.

The error log line that the boundary already wrote, and still writes, logs the
pydantic `errors()` verbatim including `input`. On the reproduction above that
put the full profile label in the log file. Out of scope here and not changed,
but it is the same value the envelope deliberately withholds.

A tree-wide collection run over the entrypoints package was red on arrival from
peer work in flight: `_external_grounding.py` imports `elided_prose` from `core`,
which does not export it at HEAD. Confirmed foreign by reading HEAD, left
untouched, and verification scoped to the owning surface. The same peer landing
owns the only API-stub drift reported by the docs scaffold check, so the
generator was not run.

The commit went through a temporary index and a compare-and-swap on the branch
ref: the shared index lock was held continuously for more than five minutes
while peer commits kept landing, so the contention was live rather than residue.
The lock was not touched. The staged set was verified after the fact and carries
twelve files, all authored here.
