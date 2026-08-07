---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:1a9e15e456db1e75769b008b164a12d7ad2cb61b00a5c1d00422f49c6a4cc084'
step_id: 'S86'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Add the transcriptive regime_legend field to ExtractedInvoiceFields and InvoiceDraft carrying the printed statutory legend verbatim with its anchor at parity with every other copied field, gated by a strict roundtrip populating it non-default and an anchor test proving an unprinted legend yields no value

## Scope

- `src/cadrumo/llm`
- `src/cadrumo/application/ledger`

## Description

- Add the row to the one field-form declaration, as free text: the legend is a
  printed phrase, so it needs no new grounding branch and gets the same
  copy-verbatim treatment every other transcribed field has.
- Carry it through the response schema, the anchor mirror, the grounding dispatch
  and the draft, and let the parity gates drive that rather than checking by
  hand.
- Populate it off-default in the strict-roundtrip fixture, and pin that an
  unprinted legend yields no value and no envelope.
- Pin the boundary the ruling drew, at the place it would be crossed: a response
  carrying a legend must leave the draft's category slot untouched.

## Outcome

The legend is transcribed exactly like every other copied field, which is the
whole content of the claim: it is evidence, not a conclusion. The value is the
phrase in its declared form, the anchor is the longer printed run it was read
from, and the two stay distinct so the later occurrence check has something to
verify rather than a byte-identical restatement.

Adding one row again reddened four gates until every consumer had gained the
field. That is the third time the single declaration has been exercised rather
than asserted, and it is worth noting that the failures were not obstacles: they
were the mechanism reporting that a derivation had been left behind.

The absence case is gated as carefully as the presence case. A document printing
no mention leaves the field null with no provenance envelope, so nothing defaults
a regime onto a plain invoice -- the failure mode that would matter most, because
a wrongly-asserted regime reads as evidence the paper never carried.

## Verification

    pytest src/cadrumo/llm/tests/test_regime_legend_vocabulary.py -n0 -p no:randomly -q
    22 passed in 41.09s

    pytest src/cadrumo/llm/tests/test_invoice_field_contract.py src/cadrumo/llm/tests/test_invoice_field_anchors.py src/cadrumo/llm/tests/test_regime_legend_vocabulary.py src/cadrumo/llm/tests/test_invoice_prompt_cache_binding.py -n0 -p no:randomly -q
    112 passed in 76.16s

    pytest src/cadrumo/application/ledger/tests/test_evidence_draft_provenance.py src/cadrumo/application/ledger/tests/test_draft_projection_parity.py -n0 -p no:randomly -q
    15 passed in 4.24s

Sequential, cold interpreter, no marker restriction beyond the module's own unit
marker. Model-free and network-free: compiled prompt text, a bundled file, and
the real parser and grounder.

Before the consumers were extended, the same parity selection reported the
declaration biting on the incompleteness:

    3 failed, 79 passed in 61.42s

## Notes

The structured-document path also carries the field now, extending it beyond what
this Step covered; that edit belongs to a concurrent lane and was left in its
working copy rather than absorbed.

The wider comparison needs its tree named to be honest. The pristine export of
the then-current commit reported seven failures, but six of those were this
Step's own source already swept into the commit ahead of the fixture updates that
complete it -- a baseline polluted by partially-landed work of mine, not a
pre-existing condition. After the fixtures, one remained: the strict-roundtrip
fixture gate, which is the gate this Step is required to satisfy and which the
new field legitimately reddened until populated off-default. It now passes.
