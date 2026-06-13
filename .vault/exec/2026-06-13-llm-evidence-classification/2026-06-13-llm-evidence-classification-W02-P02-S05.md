---
tags:
  - '#exec'
  - '#llm-evidence-classification'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S05'
related:
  - "[[2026-06-13-llm-evidence-classification-plan]]"
---




# Write a provenance sidecar per corpus fixture declaring real_corpus or synthetic_generated and its source

## Scope

- `src/aeat/application/ledger/tests/_evidence_corpus/`

## Description

- Write a provenance sidecar per fixture declaring `real_corpus` (source URL + licence) or `synthetic_generated`.

## Outcome

- Every fixture carries a `.provenance.json` sidecar; a gate asserts it. Committed `1572036a8`.

## Notes

