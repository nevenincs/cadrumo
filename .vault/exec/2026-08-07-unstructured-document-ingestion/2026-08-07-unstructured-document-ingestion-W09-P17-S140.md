---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:eb24eb2e38d2434740e7543b8ac6696be4ce09c8ea6617212c3c0ce6ffae3994'
step_id: 'S140'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Refuse at setup when the taxpayer profile carries no own territory, since the operator side of every ingested invoice is a profile and censo fact consumed from the profile authority rather than a document question, so an incomplete profile is a setup-time completeness refusal and never a per-document prompt

## Scope

- `src/cadrumo/application/ledger`

## Description

## Outcome

Executed. Verified against HEAD: `_filer_establishment.py` and the confirm path carry the refusal.

**Retrospectively reconstructed on 2026-08-13 at operator direction. NOT a contemporaneous account** — nobody observed this work being done. What is recorded is that the deliverable exists at HEAD and how that was established. Per-row verification detail is in the record-gap close audit.

## Notes
