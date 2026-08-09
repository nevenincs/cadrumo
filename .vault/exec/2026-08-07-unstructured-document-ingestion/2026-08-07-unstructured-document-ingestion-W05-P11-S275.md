---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:27bcf5804d645392a71865af3d0be1d9510e7a33ead91aa68294219801ae2276'
step_id: 'S275'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Route the audit payload transport derivation through provenance_stamp_transport instead of the hand-rolled split, which yields transport-and-reader glued together (local-text today, openai-text-extract once a consented read lands), with a red-green proof over an off-host stamp

## Scope

- `src/cadrumo/application/ledger/_llm_classification.py`

## Description

## Outcome

## Verification

## Notes
