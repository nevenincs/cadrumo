---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:05104138c4ddfc1800b13f07ca78fed2a0948ef9c3078b0331238f1ab9ba903c'
step_id: 'S268'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Accept the displayed digest as a candidate selector on the evidence review surface, since the operator can already DECIDE between two redacted candidates on the surviving note field but cannot EXPRESS the decision - resolve requires the literal value string and resolved_blockers refuses anything absent from candidate_values - and the chosen value is never consumed beyond that membership check, so it need not cross the confidentiality boundary for the choice to be expressible - match a supplied token against the redacted form as well as the raw value, which costs zero disclosure and strengthens the gate because a digest matching an offered candidate is provably a choice rather than an assertion

## Scope

- `src/cadrumo/entrypoints/cli/_ledger_evidence`
- `src/cadrumo/application/ledger/_confirmation_gate.py`

## Description

- Read the review surface before choosing between the three proposed remedies,
  and measure what an operator actually sees for an ambiguous identity.
- Accept the digest the surface rendered as a candidate selector, alongside the
  value, so a decision the operator can make is one they can express.
- Name the digests rather than the raw candidates in the refusal.
- Guard the discriminator this ruling depends on, in the surface that owns the
  capability rather than only in the funnel that could break it.

## Outcome

Modified: `src/cadrumo/application/ledger/_confirmation_gate.py`,
`src/cadrumo/entrypoints/cli/_ledger_evidence_cli.py`,
`src/cadrumo/entrypoints/cli/_ledger_evidence_review_cli.py`, the four locale
catalogues, and `application/ledger/tests/test_confirmation_gate.py`. Added
`application/ledger/tests/test_choose_candidate_by_rendered_digest.py`.

**The row's premise is half wrong, and measuring the surface is what showed it.**
Two redacted candidates are NOT indistinguishable: each carries a `note` saying
where on the page it was printed, and that note survives the funnel because it
holds no identity. Measured, an ambiguous supplier identity reaches the operator
as two digests annotated `printed under 'Proveedor'` and `printed under
'Cliente'`. An operator holding the document can decide between those.

**What they could not do was express the decision.** The choose-candidate
resolution matched on the value, which the surface had deliberately withheld, so
the only operator who could answer was one who already held the value -- which
excludes exactly the operators this surface exists for. **The defect is the
SELECTOR, not the disclosure.**

**The decisive fact: the chosen value is never consumed.** It is read once, in
the membership check, and never again; the confirm takes the identifier from the
operator override or from the draft. The value attests WHICH reading was chosen
and never becomes the record's data, so it never needed to cross the boundary.

All three proposed remedies were therefore rejected, each on its own terms. A
masked partial pays a residual disclosure to buy a discriminator the surface
already carries free. A separate adjudication channel adds a boundary to solve
one predicate. Ruling the surface out would retire a working capability over a
selector bug.

**Digest-as-selector strengthens the guarantee rather than trading against it.**
A digest matches only a reading the document actually offered, so it is provably
a choice rather than an assertion -- which is precisely what the refusal message
says the gate enforces, now structurally true instead of true by convention. The
value form stays accepted for an operator reading off the document.

The refusal now enumerates digests. Printing the competing values put the very
identity the blocker protects into a refusal message.

## Verification

    uv run --no-sync pytest src/cadrumo/application/ledger/tests src/cadrumo/entrypoints/cli/tests/test_ledger_evidence_confirm_cli.py -n0 -q -m "unit or integration"
    10 failed, 1278 passed, 16 warnings in 547.42s (0:09:07)

Seven were the absent local reading runtime on this machine, refusing before any
application code runs. One was this lane's own in-scope regression, described
below. The remaining two -- a persisted-fact roundtrip and a structured-path
closure finding -- fail identically with this change neutralised at runtime, and
both files are clean, so they are pre-existing at HEAD.

    uv run --no-sync pytest <the two gate suites> -n0 -q -m "unit or integration"
    23 passed in 1.18s

That reading is of a tree byte-identical to HEAD for every file this Step
touches.

Mutation-proved from outside the repository, both directions: restoring the
value-only match reds the two cases that name a reading by its digest, and
accepting any token reds the three refusal cases -- including the digest of a
reading the document never offered, which is what proves the gate is still a
gate.

## Notes

One in-scope regression, absorbed: the existing refusal case asserted the raw
value appeared in the message. That assertion encoded the disclosure this change
removes, so it was corrected to the new contract rather than the message being
kept to satisfy it.

The ruling has a load-bearing dependency on the candidate `note` staying
unredacted. If the funnel ever widens to eat it, adjudication stops working with
no error and no refusal. A case asserting the note survives is carried here, in
the surface that owns the capability, because a dependency guarded only at the
far end is guarded by another lane's discipline.

The operator-facing half was necessary rather than cosmetic: a selector nobody
is told about is unreachable. Both `--resolve` help strings were updated in all
four catalogues through the locales CLI.
