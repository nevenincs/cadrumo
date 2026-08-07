---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:0f4fc8ce9de4ce710400ac7ccbc125b3336e3c4d9cc37ab78bfb64311cd6497a'
step_id: 'S121'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Establish the customer tax status on the read path, since the classification assembly requires it and neither VIES nor an operator assertion is reachable while a document is being read, so it joins the two residencies among the axes an ordinary domestic invoice cannot supply. The declared-facts channel already carries the operator route as an attributed fact, so the work is reaching the point where the operator can answer rather than inventing a second supply mechanism. VIES stays deferred per the governing amendment and must not be reintroduced here

## Scope

- `src/cadrumo/application/ledger`

## Description

- Rule on what a printed customer tax identifier establishes without VIES, and record it in the module docstring.
- Make the customer-status demand lazy: raise it only where the rule table's verdict can turn on the answer.
- Generalise the existing supply-nature indifference probe to judge one undetermined axis at a time.
- Guard the probe against the no-rule-matched sentinel, so identical-because-unplaced cannot read as identical-because-indifferent.
- Supply the unresolved status member where the axis cannot matter, and never a substantive one.
- Add six gates covering the payoff, the surviving refusal, the unplaced guard and the safety asymmetry.

## Outcome

The ruling: a printed, well-formed customer tax identifier establishes that the
counterparty is acting as a taxable person, and nothing more. It does NOT
establish `B2B_IVA_REGISTERED`, because that member is the trigger for the
intra-community supply exemption and the exemption requires the customer's VAT
identification number to be verified as valid — which a number merely printed on
a page has not been by anyone. It equally does not establish
`B2B_NOT_REGISTERED`: absence of proof of registration is not proof of
non-registration. That ruling was already settled in the tree by the preceding
transcription work and is confirmed rather than reopened here; nothing printed
settles the axis deterministically, and VIES stays deferred.

What was NOT settled, and is the substance delivered, is that the demand was
being raised unconditionally. Measured against the real rule table, the ES-to-ES
domestic rule reads the customer's status only to route the three reverse-charge
kinds and the exempt immovable supply, none of which a printed goods-or-services
reading can produce. So on an ordinary domestic invoice all five statuses reach
the identical category, and the blocking gap was asking the operator a question
with no consequence, on the commonest document there is. The demand is now lazy
on exactly the terms the supply-nature axis already established, and an ordinary
domestic invoice assembles and classifies end to end.

The refusal survives where it earns its keep: an intra-community operation still
refuses on the status, naming VIES or an operator assertion, because the art. 25
exemption genuinely turns on the answer. A third-country export assembles without
the status while still demanding the supply nature, which is the per-axis
attribution working — a single sweep over the product of both axes would have
demanded an answer the law does not turn on because a different axis did.

The safety asymmetry is structural rather than probe-dependent. Where the axis
cannot matter the assembly supplies the unresolved member, which satisfies no
status predicate in the rule table and so can never trigger a rule on evidence
nobody supplied. A substantive placeholder would have rested entirely on the
probe having been right.

No second supply route was introduced: the existing declared-facts channel
already carried the attributed operator assertion, and it is used unchanged.
The held evidence-draft minting sites were not touched.

## Verification

Owning gate, sequential:

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_classification_assembly.py -n0 -q
    23 passed in 6.83s

Both lanes across the two packages the change reaches:

    uv run --no-sync pytest src/cadrumo/application/ledger/tests src/cadrumo/domain/iva/tests -n0 -q -m "not integration"
    1315 passed, 21 deselected, 15 warnings in 283.89s (0:04:43)

    uv run --no-sync pytest src/cadrumo/application/ledger/tests src/cadrumo/domain/iva/tests -n0 -q -m "integration"
    21 passed, 1322 deselected in 93.95s (0:01:33)

Lint and format, clean on both changed files:

    uv run --no-sync ruff check <changed files>
    All checks passed!

Mutation proofs, applied at plugin module scope from outside the repository so
nothing under source changed. Each run confirmed the patch landed by asserting
its banner before reading the result; four mutations, four bites:

    substantive placeholder instead of the unresolved member  -> 1 failed, 22 passed
    unplaced-sentinel guard removed from the probe            -> 2 failed, 21 passed
    the fork judgement forced to never demand anything        -> 5 failed, 18 passed
    a substantive rule widened to accept the unresolved member -> 4 failed, 19 passed

## Notes

The substantive-placeholder mutation was GREEN on the first attempt and the gate
was unsound, not the mutation inert. Where the probe certifies indifference a
substantive placeholder reaches the same category by construction, so a
category-only assertion cannot see it. The harm is not the verdict but the
record: the criteria carry the status onward to whatever reads the field rather
than the category, so a substantive placeholder writes a claim about the customer
that nobody made. A gate asserting the stamped VALUE was added and the mutation
then bit. The first diagnosis attempt was itself wrong — an unreliable
environment-variable hand-off through the runner made the harness look like it
had failed to patch, and only the banner check distinguished the two.

Two tree-wide gates are red and neither names a file in this Step's surface. The
type checkers report diagnostics in the place-of-supply, rate-box-partition and
batch-ingest modules among others; the import-hygiene debt and docstring
core-struct link gates name the aggregation and foreign-asset test surfaces.
Grepping both logs for this Step's two files returns zero occurrences, and those
files are unmodified against HEAD, so the failures are pre-existing peer surfaces
rather than this change, and were left for their owners.

The changed files were committed into HEAD by the repository's in-flight sweeper
lane across several of its own commits rather than by a commit from this Step.
The landed content was re-verified after the fact: the working tree is identical
to HEAD for both files, and the owning gate plus all four mutation proofs were
re-run against HEAD content with the same results quoted above.

No production caller consumes the assembly yet; the convergence at the
evidence-draft minting sites is deliberately held and was not touched.
