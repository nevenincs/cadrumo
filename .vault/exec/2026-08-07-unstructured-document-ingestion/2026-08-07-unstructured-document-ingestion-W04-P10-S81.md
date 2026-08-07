---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:26c5bd912dc2966277d9e500c25d87f31b84e32065c8bfda07850d12e76347eb'
step_id: 'S81'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Report the model tier beside every harness figure, record the claude-sonnet-4-6 REC-DOM-IMG-008 result (7 of 8, zero fabricated) as an upper reference point, and re-establish the baseline at the Haiku-tier proxy and the 2B-4B on-host class, gated by the harness refusing a result row missing its tier

## Scope

- `dev`

## Description

- Add the closed model-tier set, naming each member by the role it plays in the decision: the on-host small class, the cloud design proxy, and the upper reference.
- Make the tier a required field on every result row, and print it beside every figure the report renders.
- Refuse a row that arrives as data without a tier, or with an unknown one, naming the accepted set in the refusal.
- Derive baseline eligibility from the tier, so only the two design-target tiers may inform an acceptance floor.
- Record the frontier reference point as its own type, which has no accuracy to read and refuses to be recorded at a baseline-eligible tier.
- Attach the reference point's qualifying conditions as a required non-empty caveat list.
- Add the gate: the tier refusal at both the typed and the data boundary, and the reference-point anchors.

## Outcome

The tier is the axis that decides whether a figure describes the product or merely bounds it, so it is modelled as that decision rather than as a label. Members are named for the role they play — the on-host small class the product ships, the cloud proxy standing in for the design target, and the upper reference — because the question a reader actually has is whether a number bounds the product or describes it, and a vendor-named tier would need that translation performed from memory every time it was read. Baseline eligibility is a property of the tier, so a frontier figure structurally cannot set a floor.

The refusal is stated at both boundaries because they fail differently. The typed row makes the tier mandatory for anything built in process; the data-boundary check covers where an omission would actually arrive, which is a persisted result file or another tool's output. The refusal names the accepted set, since one that does not list the valid values only restates the problem.

The reference point is a separate type from a result row, and that separation is the substantive decision here. It was not produced by this harness against this key's denominators, so giving it the row type would let it flow into a baseline calculation that must never see it. It carries no accuracy property, it refuses construction at a baseline-eligible tier, and its caveats are a required non-empty field — an unqualified reference point is indistinguishable from a baseline, which is exactly the confusion the type exists to prevent.

**The reference point's denominator is not the key's, and that is a finding this Step surfaced.** The reported 7 of 8 is scored over a probe-selected subset of eight fields. The pinned key authors twenty non-null fields for that document, plus five null-truth fabrication traps. The subset is not defined by the corpus, so 7 of 8 cannot be reconstructed from the key and must never be restated as a key-denominated accuracy. The row builder would have refused it outright on the denominator mismatch, which is how it came to light; the observation is kept, with the discrepancy recorded as one of its caveats and anchored by a test asserting the two numbers still differ.

Three further conditions travel with that figure so it cannot be quoted bare: it is an upper reference and not a baseline; it was measured before the field-form contract landed, so its single miss is a printed-percent form mismatch that penalised instruction-compliance rather than reading, and it therefore understates the model and cannot be compared like-for-like against later runs; and its model revision was never recorded, so it cannot be reproduced against a pinned build. Its document is a Spanish photograph, so the corpus optimism-bias caveat applies to it as well and is attached automatically from the key rather than restated by hand.

## Verification

    uv run --no-sync python -m pytest dev/ingest_harness/tests -q -p no:randomly -n0
    23 passed, 12 deselected in 0.26s

    uv run --no-sync python -m pytest dev/ingest_harness/tests -q -p no:randomly -n0 -m integration
    12 passed, 23 deselected in 0.47s

Collected-versus-deselected read from the log files on disk: 23 of 35 in the unit lane, 12 of 35 in the integration lane, 35 total with none unaccounted for.

The refusal was also exercised directly rather than only through the suite. Passing a payload carrying a document id and an accuracy but no tier returns the refusal naming the accepted set, which is the mandated demonstration:

    result row for 'REC-DOM-IMG-008' carries no model_tier. A figure without its tier is as
    unfalsifiable as one without its key hash ...

Two mutation proofs cover this Step's gate, both driven from a throwaway plugin on the interpreter path outside the repository.

Making the data-boundary check permissive — quietly defaulting to a tier instead of refusing, which is the regression that lets an untiered figure be published — reds four tests: all three missing-tier parametrisations and the unknown-tier assertion.

Making the tier optional on the typed row reds exactly one test, the in-process refusal.

Every refusal assertion in this Step sits behind a positive control asserting the complete row builds through the same route first, so a refusal cannot pass for the wrong reason.

## Notes

The reference point's model revision is recorded as unrecorded rather than invented. A plausible-looking revision string would make the observation appear reproducible when it is not.

The baseline is re-established at the design target by construction rather than by measurement: this Step builds the instrument, and the measurement Steps that set the floors consume it. No measurement was run and no model was loaded or called in this Step.

Six peer-owned failures in the wider dev tooling suite were recorded and not patched; none names this package.
