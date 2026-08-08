---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:6abd75e82dc45861010df83e1276f9caed12d5e1704017098fecfa9206c035f1'
step_id: 'S190'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
## Description

- Add a typed nullable identification axis to the persisted counterparty fact, beside the territory it already remembers.
- Extend the fact's builder and its declared-fact projection, returning `None` rather than a value when the operator has not answered.
- Give the writer its rules: a new identification is an addition, a different one refuses naming both values, and an absent one never erases a stored answer.
- Carry the confirmed identification on the resolution the ladder consumes.
- Fall back to the remembered identification in the establishment ladder where the printed prefix reads nothing.
- Add the operator's input as a typed enum option on the counterparty confirm verb, and emit the fact on its payload.
- Add the help string to all four locale catalogues.

## Outcome

The registration fact is now asked once per counterparty rather than once per
document. That was the row's whole justification and the reason the per-document
surfaces could not satisfy it: a declared-facts entry dies with the draft, and a
ladder result describes one page.

The ladder fallback is what makes it functional rather than merely stored. The
printed prefix stays terminal where it reads, and the remembered answer fills the
gap where it does not -- which is the ordinary case, not the exceptional one,
because a bare Spanish CIF prints no prefix at all. Without it the stored answer
was unreachable for exactly the counterparties an operator most often has to
answer for.

The asymmetry between the two axes is deliberate and is the part worth reading
twice. Territory and identification take the same conflict rule, but an
identification arriving where none is stored ANSWERS a second question rather
than replacing an answer, so it is written through. A call supplying none leaves
a stored answer standing: `None` is an unasked question, and treating it as an
answer would let a caller correcting only a note silently withdraw a
registration and withhold an exemption already confirmed.

## Verification

    uv run --no-sync pytest src/cadrumo/application/ledger src/cadrumo/entrypoints/cli -m unit -n0 -q
    2 failed, 2043 passed, 3244 deselected in 200.29s (0:03:20)

Neither failure is on this surface. One is a CLI module-size budget on a module
this Step does not touch, already over budget before it began; the other asserts
a parsed supplier country code and belongs to a concurrent lane whose parser and
test are both dirty in the tree.

    uv run --no-sync pytest <the counterparty fact, roundtrip and establishment suites> -m unit -n0 -q
    36 passed in 7.95s

Live surface, confirming the typed option renders its accepted set:

    uv run --no-sync aeat app ledger counterparty confirm --help
    --identification-state <at|be|bg|cy|cz|de|dk|ee|es|fi|fr|gr|hr|hu|ie|it|lt|lu|lv|mt|nl|pl|pt|ro|se|si|sk|xi>

Mutation from outside the repository, removing exactly the no-erase rule while
preserving the conflict rule beside it:

    [MUT] plugin module imported (rung 1: banner)
    [MUT] rung 2: replacement writer invoked 15 times
    [MUT] rung 3: test_a_retry_omitting_the_identification_does_not_withdraw_it -> failed
    [MUT] rung 3 control: test_a_different_identification_refuses_and_names_both_values -> passed
    [MUT] rung 3 observable state change confirmed

The first attempt removed TWO rules and the control went red with the guarded
test. The ladder caught it: a mutation that reds everything proves the patch was
wholesale damage rather than a simulation of the rule under test. Preserving the
conflict rule verbatim made the flip surgical.

## Notes

The roundtrip fixture now populates the new field non-default and with a Member
State that DIFFERS from the territory beside it, so a load that re-derived the
registration from the establishment could not reproduce the value. The
anti-tautology proof keys on inequality rather than refusal, because the field is
legitimately nullable and the model cannot raise on its absence; a control
re-saves the unmodified envelope through the same surgery first, so the
inequality cannot be an artefact of the surgery.

Naming debt, stated rather than silently carried: the record is still called an
establishment fact while it now holds two facts. Renaming it reaches the class,
its repository, its storage namespace key, the CLI and the payloads, which is one
atomic relocation and its own row rather than a rider on this one.

The locale gate reports two ORPHANED keys for the establishment CLI option a
concurrent lane renamed. They are that lane's to retire; removing them here would
break its working copy mid-flight.
