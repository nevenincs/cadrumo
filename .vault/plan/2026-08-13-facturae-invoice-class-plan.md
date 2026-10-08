---
tags:
  - '#plan'
  - '#facturae-invoice-class'
date: '2026-08-13'
tier: L1
related:
  - '[[2026-08-13-facturae-invoice-class-adr]]'
  - '[[2026-08-12-facturae-invoice-class-reference]]'
modified: '2026-10-03'
body_hash: 'sha256:fa1d51654f2ea8a044b89fe4726c24ee8259c68bfc1c9719867df57dd9c844a4'
---

# `facturae-invoice-class` plan

## Description

## Steps

- [x] `S01` - Declare the six Facturae InvoiceClass codes as a closed enum and gate it against the bundled vocabulary, so the enum and the schema extraction cannot drift. The gate reads the committed corpus artefact rather than restating the codes, which is what makes it able to fail; `src/cadrumo/adapters/inbound/einvoice/`.
- [x] `S02` - Read InvoiceClass from the Facturae header into a typed field on the parsed record, scoped to the header's own children like its siblings. An absent or unrecognised code leaves the field None and must never refuse the document; `src/cadrumo/adapters/inbound/einvoice/parsers.py`.
- [x] `S03` - Ground the draft's invoice class on the declared code where one is present - OO and CO are ordinaria, OR and CR are rectificativa - keeping the corrective-presence inference as the fallback for a record declaring nothing. Do NOT map OC or CC onto ordinaria: they declare recapitulativa, which the domain taxonomy cannot express, so they keep the operator-stated class; `src/cadrumo/application/ledger/confirmed_field_resolution.py`.
- [x] `S04` - Surface the two cases the mapping refuses to resolve: a record declaring a recapitulativa code, and a record whose declared code disagrees with its own corrective reference in either direction. Both are findings about the document rather than states to be picked between; `src/cadrumo/application/ledger/invoice_draft_records.py`.
- [x] `S05` - Gate the whole path against the corpus fixtures that already carry OO and OR rather than synthetic XML, and prove the fallback still classifies a record declaring no code. Include the mutation proof that the declared code is what decides - a record whose corrective reference and declared class disagree must not silently take the inference's answer; `src/cadrumo/application/ledger/tests/`.

## Parallelization

## Verification
