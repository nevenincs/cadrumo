---
generated: true
tags:
  - '#index'
  - '#facturae-invoice-class'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:15793a063394f4dd746e1c44452b14dd33bc84f0b24310bcecdd4f066768af27'
related:
  - '[[2026-08-12-facturae-invoice-class-reference]]'
  - '[[2026-08-13-facturae-invoice-class-S01]]'
  - '[[2026-08-13-facturae-invoice-class-S02]]'
  - '[[2026-08-13-facturae-invoice-class-S03]]'
  - '[[2026-08-13-facturae-invoice-class-S04]]'
  - '[[2026-08-13-facturae-invoice-class-S05]]'
  - '[[2026-08-13-facturae-invoice-class-adr]]'
  - '[[2026-08-13-facturae-invoice-class-audit]]'
  - '[[2026-08-13-facturae-invoice-class-plan]]'
---

# `facturae-invoice-class` feature index

Auto-generated index of all documents tagged with `#facturae-invoice-class`.

## Documents

### adr

- `2026-08-13-facturae-invoice-class-adr` - `facturae-invoice-class` adr: `the declared code grounds the class, and the two axes it carries are not collapsed` | (**status:** `accepted`)

### audit

- `2026-08-13-facturae-invoice-class-audit` - `facturae-invoice-class` audit: `implementation closeout`

### exec

- `2026-08-13-facturae-invoice-class-S01` - Declare the six Facturae InvoiceClass codes as a closed enum and gate it against the bundled vocabulary, so the enum and the schema extraction cannot drift. The gate reads the committed corpus artefact rather than restating the codes, which is what makes it able to fail
- `2026-08-13-facturae-invoice-class-S02` - Read InvoiceClass from the Facturae header into a typed field on the parsed record, scoped to the header's own children like its siblings. An absent or unrecognised code leaves the field None and must never refuse the document
- `2026-08-13-facturae-invoice-class-S03` - Ground the draft's invoice class on the declared code where one is present - OO and CO are ordinaria, OR and CR are rectificativa - keeping the corrective-presence inference as the fallback for a record declaring nothing. Do NOT map OC or CC onto ordinaria: they declare recapitulativa, which the domain taxonomy cannot express, so they keep the operator-stated class
- `2026-08-13-facturae-invoice-class-S04` - Surface the two cases the mapping refuses to resolve: a record declaring a recapitulativa code, and a record whose declared code disagrees with its own corrective reference in either direction. Both are findings about the document rather than states to be picked between
- `2026-08-13-facturae-invoice-class-S05` - Gate the whole path against the corpus fixtures that already carry OO and OR rather than synthetic XML, and prove the fallback still classifies a record declaring no code. Include the mutation proof that the declared code is what decides - a record whose corrective reference and declared class disagree must not silently take the inference's answer

### plan

- `2026-08-13-facturae-invoice-class-plan` - `facturae-invoice-class` plan

### reference

- `2026-08-12-facturae-invoice-class-reference` - `facturae-invoice-class` reference: `the code set is six values on two axes, and it is not the regulatory taxonomy`
