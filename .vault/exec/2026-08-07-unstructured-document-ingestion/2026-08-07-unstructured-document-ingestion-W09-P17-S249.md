---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:926804d75bdeca35a64fe602b92c857ed25b40dc099d9c717115fe2319feb74d'
step_id: 'S249'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Build the counterparty-only fixture the spelling assertion needs

## Scope

- `src/cadrumo`

## Description

- Establish where the filer's residency actually comes from on this path before building anything: it arrives through the declared facts, not through the taxpayer profile, so settling it is a matter of supplying the issuer's scope rather than of standing up a profile.
- Add the first fixture on this path that settles the filer and leaves only the counterparty unplaceable, which makes the catalogue-gap carve-out the only thing left deciding the outcome.
- Give the fixture its own non-vacuity proof rather than trusting it: the exemption must spare an uncatalogued counterparty AND still refuse a catalogued one, so the sparing is the carve-out working rather than the guard being inert.
- Assert the catalogue gap is forgiven whichever spelling the record states, which is now a real comparison rather than one that holds because both spellings refuse for the filer's sake.

## Outcome

The assertion has a home and the fixture is the reason. On every other fixture here both residencies are unsupplied, so the scoped exemption forgives one slot and the other still refuses; a spelling comparison over that shape passes without the exemption ever firing. Settling the filer removes the second reason to refuse and leaves the carve-out as the only variable.

This also re-settles the underlying question non-vacuously. The earlier close ruled the defect out structurally, by observing that the status is the only thing a token contributes to the resolver, so identical statuses could not diverge. The same conclusion now rests on a fixture where the exemption demonstrably fires, which is the stronger of the two footings.

The fixture should outlive this one assertion. Any question about what the catalogue-gap carve-out does, as distinct from what an unfinished filer profile does, needs exactly this shape, and its docstring says so.

## Verification

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_ingestion_category_resolution.py -n0 -q
    35 passed in 7.54s

Proved to bite by substituting an authority blind to alpha-3 tokens, which is precisely the wiring the guard's cases carried until this campaign repointed them, with the substitute's call count reported so an ineffective rebinding could not read as a pass:

    [MUT alpha-3 -> None] spelling assertion: authority called 2x -> REDS
    [MUT alpha-3 -> None] non-vacuity proof : authority called 2x -> PASSED
    [CONTROL real authority] both -> PASSED

The non-vacuity proof passing under that mutation is correct by construction rather than a gap: it compares an alpha-2 specimen against a catalogued country, neither of which the mutation touches. It has its own control in the refusal arm.

## Notes

The additions were swept into the tree by another agent's bulk commit; the commit made here carries the remainder. Both are at the committed tree and the working copy is clean.
