---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:94058f9b3262c07e1aa2282c78e15a39dce702a02d8c4fafc1365bcbf3e9de36'
step_id: 'S286'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Stop the cost estimator reporting a plausible zero for the design-target model, since estimate_cost_usd resolves an unknown model to 0 rather than refusing and its pricing table carries claude-sonnet-4-6 only - so claude-haiku-4-5, claude-opus-4-1 and gpt-4o all price at 0 for a million tokens, and every cost figure for the tier the campaign actually targets reads free

## Scope

- `src/cadrumo/llm/_client.py`

## Description

## Outcome

## Verification

## Notes
