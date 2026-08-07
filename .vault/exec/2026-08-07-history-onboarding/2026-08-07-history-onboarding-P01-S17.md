---
tags:
  - '#exec'
  - '#history-onboarding'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:2fb1a1a43cd67ae572753c3b09c097360cc97e28fbc43a2444180972586fc14a'
step_id: 'S17'
related:
  - "[[2026-08-07-history-onboarding-plan]]"
---

# add expected_filed_declaration_grid deriving a taxpayer-specific candidate modelo and ejercicio grid from TaxpayerProfile applicability and activity_start_date, verified by a test asserting the grid matches a hand-built profile fixture's expected modelos and year span

## Scope

- `src/cadrumo/application/live/_filed_data_capture.py`

## Description

- Add `ExpectedFiledDeclarationGrid` and `expected_filed_declaration_grid`, deriving the taxpayer-specific candidate grid from declared profile facts.
- Reuse the overview obligation-coverage machinery for the modelo axis through a deferred facade import.
- Promote both on the `application.live` facade.
- Add the year-axis, modelo-axis and taxpayer-specificity tests.

## Outcome

This is the LOAD-BEARING signal, so it derives every value from data the
taxpayer declared and nothing from an AEAT-served list. The modelo axis reuses
the shipped obligation-coverage partition rather than re-deriving applicability: a
modelo is a candidate when that partition does not place it in a confident
negative or out of scope.

Three judgements go beyond a literal reading of the plan row, each because the
literal reading would make the feature lie:

A modelo the registry does not model AT ALL is dropped. No declared fact produced
its verdict, so nominating it would invent an expectation the taxpayer never made
and then report the inevitable zero rows as an anomaly.

A declared activity-end date caps the year span. A taxpayer who ceased activity
is not expected to have filed afterwards, and the uncapped span would flag every
later year as expected-but-not-found.

An ABSENT activity-start date yields an empty span carrying an explicit
not-declared flag. That distinction is the whole point: an empty span read as
"nothing expected" would silently leave only the signal whose informativeness is
unconfirmed, which is the failure the dual-signal design exists to prevent.
Absence means "cannot say", never "nothing".

The surfaced-modelo argument is passed empty on purpose and the code unions both
tuples anyway, so the result does not depend on which side of a total partition a
candidate falls out of.

## Verification

    uv run --no-sync pytest src/cadrumo/application/live/tests/test_filed_history_discovery.py -q -n 0
    26 passed in 19.26s

One test asserts the derivation responds to declared facts by comparing two
different profiles' modelo sets, because a signal named taxpayer-specific that
returned one universal list would satisfy every other assertion here.

    MUTATION activity-end-cap-ignored: control=True mutated=False -> PASS (test would red)

## Notes

An earlier version of the registry-unmodeled test asserted an empty
intersection against the unmodeled-obligations constant. That constant is
currently EMPTY, so the assertion passed vacuously and would have kept passing
with the filter deleted -- caught only because the test carried a non-empty
anchor assertion on the constant itself. It was rewritten to gate the real
invariant (every nominated modelo is one the registry models), which holds
whether or not the constant is ever populated.

Landed in the peer sweep `24f8fd9add`; content verified byte-identical and not
re-committed.
