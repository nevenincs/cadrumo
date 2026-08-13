---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:0490968a1f2bdd3dfff54e8fcd89c19bd1dc75984cad7f0e24807245d81614a9'
step_id: 'S290'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Correct the corpus field mapping for the two totals. The key's grand_total is the computed identity (base 766.30 plus iva 160.92 equals 927.22) while its printed_total is what the page states (890.00), and the draft's grand_total is the PRINTED figure, so the map scores a correct read as wrong on the two divergent documents and declares printed_total unmapped on the false rationale that the draft has no printed-total field. Map printed_total to the draft and rule grand_total unmapped as a computation the reading stage does not perform

## Scope

- `dev/ingest_harness/_field_mapping.py`

## Description

## Outcome

Executed. Verified against HEAD: the corpus field mapping for the two totals is corrected.

**Retrospectively reconstructed on 2026-08-13 at operator direction. NOT a contemporaneous account** — nobody observed this work being done. What is recorded is that the deliverable exists at HEAD and how that was established. Per-row verification detail is in the record-gap close audit.

## Notes
