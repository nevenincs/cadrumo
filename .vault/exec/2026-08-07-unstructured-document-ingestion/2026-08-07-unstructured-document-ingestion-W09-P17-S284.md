---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:f9ea8814eb2fb784baf432449659dd4f7f275d6a8582c684b65ad047b9a87c47'
step_id: 'S284'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# `unstructured-document-ingestion` exec: `W09-P17-S284`

## The row's premise was partly wrong, and the real gap is sharper

The row says the draft has nowhere to put the printed total and that a reader
therefore cannot surface a printed total disagreeing with the sum. Measured at
HEAD, both halves of that are false.

`InvoiceDraft.grand_total` is documented as the labelled invoice total and is
populated by `ground_extracted_fields` straight from what the model read off the
page, with an anchor. The disagreement is already surfaced:
`printed_total_discrepancy` compares that figure against the DERIVED
`Invoice.grand_total`, and the confirm path emits an operator-facing WARNING
notice, `ledger.evidence.confirm.printed_total_mismatch`, carrying the printed
figure, the recorded one, the difference and the currency. Both ends are
covered by tests that pass at HEAD.

So the home exists and the channel is live. What did not exist was any hold on
the reading stage to put the PRINTED figure there.

The `grand_total` contract read `concept="the total payable amount"`. Every
monetary contract constrains the FORM -- digits, printed decimal separator, no
currency sign -- and form is silent on which of two candidate figures to emit.
On a document whose printed total is wrong, "the total payable amount" does not
say whether to copy the page or to correct it. The sibling transcriptive fields
show the vocabulary was available and unused: `regime_legend` says "copy the
phrase exactly as printed".

The consequence is narrow and total. On the only documents where the answer
changes the record, the emitted figure was undetermined, so the downstream
cross-check compared an indeterminate figure against a derived one and its
result meant nothing.

## What the corpus actually holds

Twenty-nine pinned slots carry `printed_total`. Twenty-seven state exactly what
`grand_total` states. Two do not: they print 890.00 against a base of 766.30 and
tax of 160.92, which sum to 927.22, and their key lists the planted defect
verbatim as "Total impreso no cuadra con la suma de bases e IVA".

That measurement also settles the two keys' meanings, which the harness has
backwards. The key's `grand_total` is the computed identity and its
`printed_total` is what the page states, while the draft's `grand_total` is the
printed figure. So the harness maps the key's computed total onto the draft's
printed one and scores a correct read as WRONG on both divergent documents, and
it declares `printed_total` unmapped with the rationale "the draft has no
printed-total field" -- which is not true. Out of this Step's scope; opened as
`W09.P17.S290`.

## What landed

The contract now tells the model to copy the printed figure even when it does
not equal the sum, and never to recompute or correct it. Nothing reconciles at
read time: deriving the correct total stays with `build_catalogue_invoice` and
the identity stays with `domain/invoices/_decomposition.py`, so no second
arithmetic authority was created.

The gate pins three properties. A printed total contradicting the lines is
recorded as printed and specifically not as the sum. A total that agrees is
still recorded, which is the positive control. And an unprinted total stays
`None` -- never zero, never the sum -- so absence remains representable for the
ordinary document that carries only line items.

Fixtures are the corpus's own divergent figures, rendered as the JSON a reading
model emits and parsed by the production parser. A fixture authored to agree
with itself could not fail on the defect the corpus actually plants, and one
built from the already-parsed object would skip the stage under test.

## Proof

Five mutations from a plugin outside the repository; no tracked file touched.
Baseline 4 collected, 4 passed. Every mutation flipped.

Two discriminate. Making the reader recompute the total as base plus tax reds
the divergence assertion while the positive control stays GREEN -- the failure
is the substitution, not a dead field. Making the reader never populate the
field at all reds the positive control AND the divergence assertion, which is
what makes "records the printed figure" distinguishable from "records nothing".
Collapsing an absent total into the sum, and into zero, each red the absence
assertion; reverting the contract wording reds the contract assertion alone.

## Verification

    uv run --no-sync pytest src/cadrumo/llm/tests -n0 -q -m unit
    442 passed, 4 deselected

The whole package lane was run rather than the new module alone, because the
contract text is rendered into the compiled prompt and a prompt change can move
a cached prompt identity. Nothing moved.

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_evidence_draft_printed_total.py -n0 -q
    5 passed

Run to confirm the consumer end of the channel still holds, since this Step's
value only matters if something reads it.

`ruff check`, `ruff format --check` and `ty check` clean.
