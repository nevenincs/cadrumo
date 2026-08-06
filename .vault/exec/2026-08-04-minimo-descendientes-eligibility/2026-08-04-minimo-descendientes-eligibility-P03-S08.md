---
tags:
  - '#exec'
  - '#minimo-descendientes-eligibility'
date: '2026-08-04'
modified: '2026-08-04'
body_schema: 'body-v1'
body_hash: 'sha256:5ca1449238174194adf81d7439b8fbaffcaf6d9a30538a98b4feb6e3afdf13fe'
step_id: 'S08'
related:
  - "[[2026-08-04-minimo-descendientes-eligibility-plan]]"
---

# Add the three new facts to the interactive descendiente flow, its prompts and its renderer, and correct the flag help string which still lists only the original keys so an operator refused at the write door cannot discover from help how to express the rentas figure, updating the four locale catalogues for that string through the locales CLI rather than by hand

## Scope

- `src/cadrumo/entrypoints/cli/_config/_descendiente.py`
- `src/cadrumo/application/wizard/`
- `src/cadrumo/locales/`

## Description

## Outcome

The three eligibility facts are declared on the guided descendant flow as data, in the same
tuples the existing questions use, bound through the same mechanism, with one validator
following the shape of the existing non-negative check. No prompt-handling code was written.

That outcome came from a semantic sweep rather than from the Step text. The probe for how a
guided-flow question binds to a profile fact path found the declarative page mechanism and
the canonical descendant catalogue, so the fields joined the existing declaration instead of
growing a parallel path.

The age-gate judgement call was made and declined, for a mechanical reason worth recording.
The flow's condition mechanism expresses only exact-token comparisons against an earlier
answer, and age is derived from a birth date, so a gate is not expressible declaratively.
Building one would have meant hand-rolling conditional prompt logic -- the exact signal the
brief named as meaning the canonical home had been missed. All three pages are unconditional
and optional, matching the shape the childcare question already uses.

An unanswered figure stays UNDECLARED rather than defaulting to zero, and the distinction is
load-bearing: zero is a positive claim that the descendant earned nothing, and asserting it
for an operator who skipped the page would recreate the silent over-claim this campaign
exists to close.

The consequence is stated plainly rather than glossed. This Step REDUCES the residual it was
asked to close, it does not eliminate it. An operator who skips the page still leaves the
figure undeclared, and the engine still treats undeclared as non-excluding, so a descendant
who genuinely earns above the cap can still over-claim silently. What changed is that the
fact is now expressible and discoverable through the guided flow, where before it could only
be reached by a flag.

The flag help string, which still lists only the original keys, is the remaining
discoverability gap and carries four-catalogue locale work.

Not verified: no end-to-end walk of the guided flow against a live bucket. The pages declare
and the round trip is unit-verified in both directions, but no interactive run was driven.
The three new prompts are also unreviewed Spanish prose, deliberately written without euro
figures so the copy cannot drift from the registry, at the cost of vaguer wording. A
fluent review is warranted.

REOPENED AND FINISHED. The Step was closed while part of its scope was undone, and the
executor had reported that in its own report. The coordinator read the report, wrote this
record, and checked the Step anyway. Reopened on a later self-audit rather than by a reviewer.

The flag help now names every key the parser accepts, in all four catalogues, written through
the locales CLI only.

Finishing it exposed a worse defect in the same string, and this one moved tax. The Catalan
catalogue had TRANSLATED the key tokens, accents and all. The parser upper-cases and compares
literally, so an accented token did not match, was not refused, and was silently DROPPED --
the claimed value discarded while the default stood. Measured: the accented cohabitation token
left a descendant marked as cohabiting when the operator had declared the opposite.

The direction is the one this whole campaign exists to close. A Catalan operator following the
shipped help to declare a NON-cohabiting descendant granted themselves a minimo they are not
entitled to. Help copy alone was under-declaring tax, through a surface nothing gated. The
coordinator confirmed the mechanism independently: an unaccented mixed-case token IS honoured,
so the accent was the breaking difference rather than the case.

The gate is behavioural rather than textual, deliberately, and the executor stated why: a test
asserting the help contains an expected key list would have matched the English string
perfectly and missed the Catalan defect entirely, which is exactly how it shipped. Instead it
extracts whatever tokens each locale actually advertises and drives every one through the real
parser, asserting the parsed record differs from an untouched baseline. A token the parser
ignores fails the gate whether it was mistranslated, renamed, or never implemented. Proved
non-vacuous by replaying the pre-fix Catalan string through the assertion logic in memory, so
no shippable window opened.

A discovery probe also settled the open question about where to point operators: the group
with no subcommand already opens the guided door onto the descendant repeating group, which is
where this Step declared the three fields. So the help now names the flag contract for
non-interactive callers and points humans at the guided door, rather than expecting someone to
meet a rentas question they did not know to ask through eleven KEY= tokens. No euro figure
appears anywhere, pinned by its own test so it cannot creep back.

Not verified, and one of these is a live risk rather than a nicety: the trailing prose in three
locales is unreviewed by a native speaker, and NO SWEEP was run for the same translated-token
class elsewhere. Any other flag parsing key-value tokens from a locale-backed help string could
carry the identical silent-drop defect. That sweep is dispatched separately.

## Notes
