---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:952d60138aab41fb02c10a39cdaf08fe2bd430e1bf16fccf72a515c46dd2668d'
step_id: 'S139'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Prove the ladder never defaults to the peninsula with a fixture whose invoice prints a bare B-CIF, no country and no gated postal evidence, asserting unknown and never the mainland, mutation-proven. Add the companion probe feeding a Paris five-digit code with the country gate removed and asserting it reds, since Spain France Germany and Italy all use five-digit codes so the shape guard discriminates nothing and a Paris code otherwise resolves to the Spanish peninsula

## Scope

- `src/cadrumo/application/ledger`

## Description

- Gate the ordinary domestic document: a checksum-valid company identifier, no country and no postal evidence must refuse both residencies.
- Sweep every reachable domestic evidence shape and require none of them to resolve a residency.
- Mutation-prove the property by making an unestablished residency fall back to the peninsula.
- Record that the companion foreign-postal-code probe had already landed with the preceding Step.

## Outcome

The peninsula default is now gated rather than merely absent. The fixture is the
document the whole read path is aimed at: a checksum-valid Spanish company
identifier, no printed country, no postal evidence the country gate would admit.
It must refuse both residencies, and the assertion is on the absence of the
mainland specifically rather than on something merely being missing — a refusal
for an unrelated reason would satisfy a bare not-assembled check while the
default sat live underneath it.

The identifier is real rather than a placeholder, because that is the whole
point. It passes the AEAT checksum, so the tempting reading is that a valid
Spanish identifier makes a Spanish party. It does not: the non-resident company
leader, the K/L/M identifiers issued to Spaniards abroad and to non-residents,
and the whole NIE series are all checksum-valid Spanish identifiers belonging to
parties not established in Spain, and establishment for IVA is the sede de
actividad rather than tax registration. A malformed fixture value would have
been refused for the wrong reason and proved nothing.

One fixture proves one document, so a second gate sweeps the space instead: the
identifier present or absent, crossed with a postal code absent, empty,
whitespace, or a Spanish-looking five digits, none of them carrying country
evidence. Every combination must refuse. The postal-bearing rows are the sharp
ones, because a Spanish-looking code with no country evidence establishes nothing
on its own — the five-digit shape is shared with France, Germany and Italy.

The companion foreign-postal-code probe the row asks for had already landed with
the preceding Step, driving the join with Paris, Berlin, Rome and Reims codes and
confirmed under the ungated mutation to place a Paris issuer on the peninsula. It
was not rebuilt here.

## Verification

Owning gate, sequential, three consecutive runs:

    uv run --no-sync pytest .../test_classification_assembly.py -n0 -q
    34 passed in 4.59s
    34 passed in 4.59s
    34 passed in 4.70s

Mutation proof, applied at plugin module scope from outside the repository and
confirmed by its banner before the result was read. An unestablished residency
made to fall back to the peninsula:

    12 failed, 22 passed in 5.62s

Both gates added here are among the twelve, alongside the Spanish-country,
absent-postal, bare-postal, foreign-postal and distinct-refusal gates. The
breadth is the point: the default is caught from every direction a document can
approach it from, not only by the fixture written for it.

The mutations covering the two preceding Steps were re-run against this change
and still bite.

    uv run --no-sync ruff check <the changed test file>
    All checks passed!

## Notes

**A transient failure worth recording, because its mechanism is in this Step's
own code.** One run reported the domestic supply-nature gate failing, demanding
the supply kind on a branch that does not fork. It did not reproduce in three
subsequent sequential runs, nor in isolation, and the failing run took fifteen
seconds against the usual four and a half. The rule table was measured directly
across three filing dates and does not fork on nature for a domestic operation,
so the demand was spurious rather than a real change in the law.

The plausible mechanism is this module's own indifference probe. It catches every
exception and treats an unclassifiable probe as forking, which is the correct
safety direction — an operation that could not be placed may still land on a
branch needing the answer. But it means a transient failure to read the bundled
rate data, while a concurrent lane is writing registry files, surfaces as an
operator being asked a question the law does not turn on. It fails safe and it
fails noisily, which is the right trade, but a reader seeing this gate red should
re-run sequentially before triaging it as a regression.

The identifier used in the fixture is a synthetic checksum-valid value chosen by
searching the check-digit space, not a real company's. It appears only in test
source.

No production code changed in this Step; both additions are gates over behaviour
the preceding Step landed. So there was no red-to-green cycle to demonstrate, and
the necessity of each gate rests on the mutation biting rather than on the test
having failed first.
