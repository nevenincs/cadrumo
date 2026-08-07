---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:f6e44fd8745d3693f1439edb51bab80a77bdca15a625d856db1208fe7d467aa7'
step_id: 'S115'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Give the operator review loop a draft-subject terminal carrying no numeric confidence

## Scope

- `src/cadrumo/application/ledger`

## Description

- Add a confidence-free draft subject and its decline result to the review workflow, widening the reviewed-suggestion union.
- Delegate apply to the draft store's existing single writer, keyed by bucket and evidence reference.
- Split the draft decline inside the reject branch, emitting an evidence-scoped bucket event and writing no draft.
- Add the event member the decline needs, and promote both new types to the package facade.

## Outcome

All four rulings held as given and the corrected premise held too: the dispatch takes the suggestion directly, so widening the union was the whole of the extension and nothing needed loosening.

The subject is confidence-free by construction rather than by leaving a field unset. An optional confidence would satisfy any test that merely declined to populate it while leaving the field available to the next caller, and the prohibition is load-bearing: a model's self-assessed certainty is not evidence, and a number beside a field invites an operator to treat one reading as more checked than another when nothing checked either. The subject is keyed by the evidence it was read from rather than by a transaction, because a draft exists before any ledger row does — requiring a transaction id would be requiring the answer to the question under review.

Apply delegates to the store keyed by bucket and evidence reference, so a correction updates the review in place instead of forking a second draft for one document. Reject writes no draft at all: a no-op rewrite would leave one stored draft with a fresh timestamp, exactly what a re-read that came out the same would leave, and the operator's decline — the only thing the decision produced — would be the part not recorded. The trace is therefore an event, and it needed its own member rather than a reuse of the three existing evidence events, because a decline changes no stored evidence.

The structural hazard was real and is where the work went. The reject branch runs before any type dispatch and returns for every reject, so a draft handler placed after it is unreachable and one placed before it captures rejects it does not own. Only nesting inside that branch is correct, and no behavioural test over the cases that exist today can tell the three placements apart.

## Verification

    uv run --no-sync pytest -n0 -p no:cacheprovider src/cadrumo/application/ledger/tests/test_reviewed_invoice_draft_terminal.py -q -m ""
    7 passed in 1.81s

    uv run --no-sync pytest -n0 -p no:cacheprovider src/cadrumo/application/ledger src/cadrumo/domain/buckets -q -m ""
    1 failed, 951 passed, 15 warnings in 335.52s (0:05:35)

The single failure is the bucket-event payload-bounding gate, naming a `provider` key in another lane's in-flight classification module.

Two mutations, applied from a plugin outside the repository, each reddening exactly one assertion:

    reject_writes_the_draft_back              1 failed, 6 passed
    move_the_split_beside_the_reject_branch    1 failed, 6 passed

The second is the one the row asked for. It dedents the draft check out of the reject branch, which is the placement a hurried implementation reaches for, and only the structural assertion notices — every behavioural case still passes, which is precisely why the structural assertion exists.

Two positive controls carry weight beyond their own cases. The confidence prohibition is paired with an assertion that the three sibling subjects still require the field, so the absence reads as a choice rather than as a codebase that never had one. The transaction-bound reject is exercised through the same terminal and must still reach the original primitive, so a draft branch placed too early is caught rather than hidden by draft-only assertions.

## Notes

A sharp edge found by probe rather than by reading, and deliberately not fixed here. The decline puts the operator's reason into the event payload, where values are capped at five hundred characters and refuse rather than truncate: a six-hundred character reason makes the decline refuse. The established transaction-bound rejection does exactly the same thing with the same field, so this path matches its sibling rather than diverging. Bounding one and not the other would give two reject paths different behaviour on the same input, which is worse than a shared ceiling. It is a finding about the reject vocabulary as a whole.

The static payload-bounding gate did not flag either site's operator reason — it flagged a call-expression form elsewhere — so the ceiling was established by running it, not by reading the gate's verdict.
