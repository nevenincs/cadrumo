---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:5e4f15e9d495ddfac6424b686007fe98d23707c89a9ee512ed6e3b34bb32f2bc'
step_id: 'S136'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Give a confirmed counterparty establishment fact a counterparty-level home with persistence and provenance, since establishment is a property of the entity rather than of each invoice and no such home exists at HEAD where counterparty attributes live per-invoice. The per-invoice counterparty country field is not it and asking per invoice is not the fallback. An operator assertion persists as an operator-provenance fact through the declared-facts channel and is consumed by every later document resolving to the same counterparty identity, so the cost is one question per new counterparty whose paper is non-decisive rather than a question per domestic invoice

## Scope

- `src/cadrumo/application/ledger`

## Description

## Outcome

Executed. Verified against HEAD: the counterparty establishment surfaces are present in `_confirm_establishment.py` and `_establishment_ladder.py`.

**Retrospectively reconstructed on 2026-08-13 at operator direction. NOT a contemporaneous account** — nobody observed this work being done. What is recorded is that the deliverable exists at HEAD and how that was established. Per-row verification detail is in the record-gap close audit.

## Notes
