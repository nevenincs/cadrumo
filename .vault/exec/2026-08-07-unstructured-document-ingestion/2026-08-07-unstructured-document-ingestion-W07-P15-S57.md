---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:3b356dbb7553f0245924f6b32d6b06bc9819ce92b271cfa0b789ee1a1de2496a'
step_id: 'S57'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Prove the tabular split behaviour: a known fixed-layout file imports fully on a core-only install while an unknown vocabulary refuses at the mapping call with the install hint, gated by fixtures on both sides

## Scope

- `src/cadrumo/adapters/inbound/financial`

## Description

## Outcome

Executed. Verified against HEAD: `test_tabular_extra_split.py` carries both sides the row demanded — a known fixed-layout file importing fully without the extra, and an unknown vocabulary refusing at the mapping call and naming it — plus a third case the row did not ask for, proving the refusal comes from the extra's ABSENCE rather than from the file.

**Retrospectively reconstructed on 2026-08-13 at operator direction. NOT a contemporaneous account** — nobody observed this work being done. What is recorded is that the deliverable exists at HEAD and how that was established. Per-row verification detail is in the record-gap close audit.

## Notes
