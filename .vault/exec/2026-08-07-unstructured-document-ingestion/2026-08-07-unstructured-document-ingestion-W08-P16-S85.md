---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:6009a605b56844cf378bcfe3d00015879a60cdf3f0038ce3db018512761258b8'
step_id: 'S85'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Guard the statement folder import per file so one unreadable statement is reported with its path and reason through the typed Notice channel while every other file still imports, keeping a run that imported nothing a hard refusal, gated by a poisoned-file folder fixture importing the rest and a positive control proving an all-good folder imports every file

## Scope

- `src/cadrumo/entrypoints/cli`

## Description

## Outcome

Executed. Verified against HEAD: the per-file statement-folder guard is present.

**Retrospectively reconstructed on 2026-08-13 at operator direction. NOT a contemporaneous account** — nobody observed this work being done. What is recorded is that the deliverable exists at HEAD and how that was established. Per-row verification detail is in the record-gap close audit.

## Notes
