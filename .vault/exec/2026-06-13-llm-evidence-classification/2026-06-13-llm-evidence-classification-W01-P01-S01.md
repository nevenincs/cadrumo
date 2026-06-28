---
tags:
  - '#exec'
  - '#llm-evidence-classification'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S01'
related:
  - "[[2026-06-13-llm-evidence-classification-plan]]"
---




# Thread provider Optional with lazy text-classifier resolution in suggest/saturate/split classification

## Scope

- `src/aeat/application/ledger/_llm_classification.py`

## Description

- Thread `provider` Optional through suggest/saturate/split with lazy text-classifier resolution; the dispatch helpers raise an instructive `TransactionValidationError` when the text path needs a provider and none was supplied. Suggestion `provider` fields made Optional with guarded `.value` reads.

## Outcome

- Image evidence now classifies on-host with no `--llm`; the text/cloud path still requires a provider. Committed `41c17af16`.

## Notes

