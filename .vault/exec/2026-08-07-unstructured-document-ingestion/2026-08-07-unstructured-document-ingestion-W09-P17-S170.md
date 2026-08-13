---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-07'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:5e2209d1db81da572718de400a5e0a31f3e9792972b5848d710fc503e9ec5523'
step_id: 'S170'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Correct the country vocabulary header claim that folding is not transliteration, since it is true of the diacritic-folding function it was written about and false of the composed normaliser, which performs exactly one transliteration by mapping the eszett to a double s through Unicode full case folding. One sentence, routed as its own row because the lane that found it had already been wrong about this same mechanism once and declined to give a third unreviewed opinion on it

## Scope

- `src/cadrumo/_data/registry`

## Description

## Outcome

Executed. Verified against HEAD: the country-vocabulary header claim is corrected.

**Retrospectively reconstructed on 2026-08-13 at operator direction. NOT a contemporaneous account** — nobody observed this work being done. What is recorded is that the deliverable exists at HEAD and how that was established. Per-row verification detail is in the record-gap close audit.

## Notes
