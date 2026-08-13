---
tags:
  - '#exec'
  - '#facturae-invoice-class'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:da8a4f17029f4e0a86efb45e180b837e7e4f0000b5e3bfd75dd82c4bae2ff7ea'
step_id: 'S01'
related:
  - "[[2026-08-13-facturae-invoice-class-plan]]"
---




# Declare the six Facturae InvoiceClass codes as a closed enum and gate it against the bundled vocabulary, so the enum and the schema extraction cannot drift. The gate reads the committed corpus artefact rather than restating the codes, which is what makes it able to fail

## Scope

- `src/cadrumo/adapters/inbound/einvoice/`

## Description

- Declare `FacturaeInvoiceClass` as the closed six-member wire vocabulary.
- Export the typed axis through the owning adapter facade.
- Compare the enum values with the committed Facturae schema extraction.
- Verify the extraction retains its official-source provenance.

## Outcome

- The adapter now owns a typed Facturae invoice-class vocabulary without conflating it with the domain invoice taxonomy.
- The focused adapter gate passed with two real assertions derived from the bundled extraction.

## Notes

- Semantic discovery succeeded and located the nearest corpus-grounded vocabulary gate.
- Verification was scoped to the files and test introduced by this Step; repository-wide readiness was not evaluated.
