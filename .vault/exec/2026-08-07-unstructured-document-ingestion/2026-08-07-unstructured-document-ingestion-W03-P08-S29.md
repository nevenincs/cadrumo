---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:72241ef85002c1b810595fbb51430e58d9921ad4c983ca5315de05ca7fb0a0de'
step_id: 'S29'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Enrol the mapping lane as statement-import fallback strictly after the exact fixed-layout providers, gated by a known-bank fixture still taking the exact provider and an unknown-format fixture reaching the mapping lane

## Scope

- `src/cadrumo/adapters/inbound/financial`

## Description

- Add `_mapped_tabular.py`: the fallback provider, its required-role contract,
  and the single wiring point through which detection obtains a mapping.
- Split the exact fixed-layout ordering out of the detection dispatcher and
  append the fallback after it in every branch.
- Rewrite the existing candidate-coverage test from a hardcoded provider tally
  onto the ordering property.
- Export the lane through the providers and financial facades.

## Outcome

The fallback is appended after every exact fixed-layout provider, in every
detection branch, and never ahead of one. A known bank export keeps taking its
exact parser.

The load-bearing test is not that the fallback comes last but that it *would
have taken the known bank export had it been offered it first*. Without that,
ordering the lane last would be protecting nothing and the ordering assertions
would pass for the wrong reason — the lane could be incapable rather than
deferred.

A file is never refused whole. An unmapped column is reported; a row that will
not parse is reported and skipped while every other row still imports;
validation performs a full dry projection so the operator sees every problem
before ingest rather than one row at a time.

The existing candidate-coverage test asserted an exact tally of four providers.
Enrolling a fifth made it fail for saying nothing about coverage, which is the
failure mode a hardcoded count always has. It now gates on the property: every
exact provider offered, each exactly once, fallback last.

## Verification

The enrolment tests together with the detection tests they change:

    uv run --no-sync pytest src/cadrumo/adapters/inbound/financial/providers/tests/test_mapped_tabular_fallback.py src/cadrumo/adapters/inbound/financial/providers/tests/test_detection_ordered.py -p no:randomly -n0
    16 passed in 2.96s

The whole owning package, confirming no regression in the exact providers:

    uv run --no-sync pytest src/cadrumo/adapters/inbound/financial/ -p no:randomly -n0
    142 passed in 5.71s

Mutations applied from a throwaway plugin outside the repository, so no tracked
file changed. Placing the fallback ahead of the exact providers, with a resolver
good enough to claim a bank export, reddened seven tests.

**Corrected after a later review pass.** That mutation supplied a resolver the
lane could act on, and the claim originally recorded here — that it reddened the
known-bank outcome test, "the gate this Step exists to install" — held only
because of that supply. Re-run with the PRODUCTION resolver ordered first, the
outcome test stays **green**: under test the resolver reaches a model and a
profile-bound cache that are unavailable, so the lane declines every file
wherever it sits in the order, and the export keeps its exact parser because the
fallback cannot act rather than because the ordering protects it. The shadowing
regression was therefore unguarded by that test.

The guarantee now rests on a structural assertion instead: the matching
provider's position in the candidate order is compared against the mapping
lane's. That reddens when the lane is ordered first whether or not its resolver
could have answered, and it is proved in both directions — the production lane
ordered first **reds** it, and a genuinely capable lane ordered last leaves it
**green**, so it measures position rather than incapacity. The outcome test is
kept, restated as an outcome check that does not on its own establish the
ordering.

## Notes

This Step deliberately shipped the lane inert, its wiring point returning no
resolver, so a file reaching it got a named diagnostic rather than a guess.
Writing a header-alias resolver here would have forked the semantic mapping
capability the sibling Step owns, and a second mapper is exactly the
fragmentation this campaign exists to avoid.

The sibling Step has since bound the semantic mapper at that wiring point, and
nothing else in the module changed — the seam held. One test of this Step had
pinned the inert state itself (asserting the wiring point returns nothing) and
went red the moment the binding landed; it had encoded a scaffold state as a
contract. It was replaced by tests of the invariant that actually matters: an
unmappable file reports and refuses rather than guessing, and the wiring point
remains the lane's only production mapping source. The ordering gates passed
unchanged across the binding, which is the stronger result — a known bank export
still takes its exact parser now that the fallback is genuinely live.

The shared role vocabulary carries no bank-statement members: no booked date, no
movement amount, no direction. The statement lane therefore reads a booked date
under the invoice-date role and a movement amount under the grand-total role,
documented at the required-roles declaration. This is a semantic stretch and is
raised for the vocabulary's owner rather than resolved here, since adding members
would mean editing another lane's package and the assignment barred a parallel
role set.

Two repository-wide gates were red on arrival and were left untouched: the
import-hygiene gate on a test in the language-model package, and one docstring
cross-link assertion in the aggregation package. Neither names any file of this
Step; the docstring log was grepped and carries no occurrence of this package.

The type checker is not installed in this environment, so the new modules are
lint- and test-verified but not type-checked here.
