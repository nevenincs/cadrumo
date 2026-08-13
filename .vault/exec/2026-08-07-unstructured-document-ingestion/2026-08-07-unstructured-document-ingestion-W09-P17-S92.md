---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:44751150ca5ebf5e7fcbcadd7ed5277910af4b5923eef4bce66e71a4f19a6e4b'
step_id: 'S92'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Drive the extract and confirm CLI commands end to end and assert the emitted envelope actually carries the provenance envelopes and discrepancies, proving reachability rather than schema registration, since the existing parity gate hand-builds its payload and neither CLI test mentions provenance

## Scope

- `src/cadrumo/entrypoints/cli/tests`

## Description

## Outcome

Executed. Verified against HEAD: `test_evidence_provenance_reaches_the_operator.py` drives extract and confirm end to end and asserts the emitted envelope carries both provenance and discrepancies, including an arithmetic disagreement reaching the extract envelope and a self-contradicting document refused at confirm.

**Retrospectively reconstructed on 2026-08-13 at operator direction. NOT a contemporaneous account** — nobody observed this work being done. What is recorded is that the deliverable exists at HEAD and how that was established. Per-row verification detail is in the record-gap close audit.

## Notes
