---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:23763522d37dbefd0adffb1bce1744e72c766f1955c095b3ae8e7661e144df8b'
step_id: 'S262'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Map each Facturae InvoiceTotals element onto the right term of the codebase identity, since NO Facturae element equals the codebase total and it has to be derived rather than read. Measured against the real parser at HEAD on a specimen built to the schema's own documented arithmetic: a Facturae invoice carrying the ordinary 15 percent IRPF retencion states InvoiceTotal already NET of it, the parser reads that element as grand_total, and the parser recovers no retencion at all, so the closure identity computes 242.00 against a stated 212.00 and exceeds it by exactly the 30.00 retencion. That is a false CLOSURE_DISCREPANCY blocking a correct invoice, live today, on the commonest Spanish professional document there is. Two arms. Retencion is the live one. Suplidos is the second and is NOT what was first reported: reimbursable expenses enter at TotalExecutableAmount and never at InvoiceTotal, so the originally rowed mechanism was wrong and the term simply has no producer. Both corpus specimens are blind to this because both are synthetic and carry neither optional term, which is a fixture-provenance instance in its own right. Blocked on one artefact: the InvoiceTotals element sequence and its four computation annotations bundled as extracted fact with a provenance stamp naming the OFFICIAL source URL, schema version, retrieval date and payload SHA-256, on the precedent of the bundled Facturae country enumeration. The text currently in hand came from a third-party mirror and must be verified against facturae.gob.es before it grounds anything

## Scope

- `src/cadrumo/adapters/inbound/einvoice`

## Description

## Outcome

Executed. Verified against HEAD: the Facturae InvoiceTotals composition is a bundled corpus artefact carrying its own provenance, mapping each element onto the right term of the codebase identity.

**Retrospectively reconstructed on 2026-08-13 at operator direction. NOT a contemporaneous account** — nobody observed this work being done. What is recorded is that the deliverable exists at HEAD and how that was established. Per-row verification detail is in the record-gap close audit.

## Notes
