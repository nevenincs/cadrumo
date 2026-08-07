---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:154460ba47e25d88981e5bcbf4ce6911f1c96bb7bea25b48f0203bb089b90423'
step_id: 'S13'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
## Description

- Declare `ROLE_EVIDENCE_KEY_SUFFIX` and `role_evidence_key_for_field` beside the anchor suffix, so prompt and parser derive one key spelling.
- Add `InvoiceFieldContract.role_evidence_instruction`, validated present exactly on the tax-identifier form and absent everywhere else.
- Derive `identity_field_names()` from the declared form rather than hand-listing it.
- Add `ExtractedRoleEvidence` and bind it into `ExtractedInvoiceResponse`; split the reply on the role suffix before the anchor suffix.
- Carry the claim onto `FieldProvenance.role_evidence`, unchecked, exactly as the anchor is.
- Add `printed_excerpt_occurs` to the anchor authority and check every claim against the transcription before it can reach the resolver.
- Render the role-evidence block and the third skeleton key into the compiled prompt; bump the template version.
- Surface the field on the operator extract and review payloads.

## Outcome

The counterparty path is open again, and it is open only for a document that
says whose identifier is whose.

The half that was missing had teeth, not volume. The reading stage previously
synthesised a string that restated its own assignment, which was true for every
candidate on every document and therefore permanently satisfied the guard that
exists to refuse an unevidenced identity. The prior Step deleted that string and
the guard began refusing correctly -- but with nothing to replace it, an
ordinary two-party invoice refused too.

What ships instead is a printed excerpt: the heading or label the reader copied,
checked against the transcription through the same search the anchor check uses.
The difference from what it replaces is not length. It is that this claim can be
false, and when it is false the identity stays unresolved rather than being
assigned on the reader's own say-so.

Measured through the production grounding path, taxpayer identity supplied:

    defect: true id fails checksum, unrelated valid survives   -> unanchored, unresolved
    single valid identifier, no role evidence                  -> unanchored, unresolved
    single valid identifier + printed role evidence            -> anchored, resolved
    two parties, filer excluded, no role evidence              -> unanchored, unresolved
    two parties, filer excluded, printed role evidence         -> anchored, resolved
    role evidence the document does NOT print                  -> unanchored, unresolved
    two competing printed headings                             -> ambiguous, both surfaced

Rows one, two and four are unchanged from the state this Step inherited, which
is the point: nothing was loosened. Rows three and five are the reopening. Row
six is the property that makes rows three and five safe to accept.

The schema stays strict and closed. A role-evidence key for a field that
declares none is refused, as is any unrecognised key; a reply carrying no role
evidence parses cleanly and simply evidences nothing, which is the fail-safe
direction because an unevidenced identity refuses.

## Verification

    uv run --no-sync pytest src/cadrumo/llm/tests/test_invoice_role_evidence.py src/cadrumo/llm/tests/test_stage_two_semantic_reader_wiring.py -n0 -p no:cacheprovider -q -m unit
    20 passed in 11.94s

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_grounded_reading_wiring.py -n0 -p no:cacheprovider -q -m unit
    22 passed in 4.17s

Mutation, applied from a plugin outside the repository, installed at plugin
module scope before collection:

    S13_MUTATION=admit_unprinted_role_evidence ... -p s12_s13_s14_mutation
    2 failed, 169 passed in 70.00s
    reds: test_role_evidence_the_document_does_not_print_is_dropped,
          test_the_reading_stage_records_the_claim_unchecked_and_the_grounding_stage_checks_it

    S13_MUTATION=drop_role_evidence_from_the_prompt ... -p s12_s13_s14_mutation
    4 failed, 91 passed in 60.85s
    reds: the two prompt-parity gates plus both role-evidence prompt gates

Both reds come from the production guard rather than from fixture setup: the
fixture transcription prints BOTH party headings, so a claim can be true or
false against it, and each dropped-evidence assertion carries a non-vacuity
check that candidates were produced at all.

## Notes

The mutation harness's first verification hook was wrong and said so loudly
rather than passing: it asserted the gate module binds `printed_excerpt_occurs`,
which it never does -- the gate binds `_identity_candidates`, and that function
resolves the guard as a module global at call time. The check now asserts the
gate's bound caller is the production object and that the production module
holds the wrapper. The mutation had landed correctly throughout; only the
instrument was checking the wrong object.

`ground_self_reported_anchor` has no production caller and had none before this
Step either. It is reachable only from its own test. Reported rather than
deleted: removing a public facade symbol and the `anchor_self_reported`
invariant it feeds is a wider decision than this Step's scope, and the invariant
itself is load-bearing and now asserted directly.
