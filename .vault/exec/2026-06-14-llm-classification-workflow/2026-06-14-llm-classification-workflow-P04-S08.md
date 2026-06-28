---
tags:
  - '#exec'
  - '#llm-classification-workflow'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S08'
related:
  - "[[2026-06-14-llm-classification-workflow-plan]]"
---




# Add reject_llm_suggestion + LLMSuggestionRejectionResult emitting the rejection event without mutating the transaction

## Scope

- `src/aeat/application/ledger/_llm_classification.py`

## Description

- Add `reject_llm_suggestion` + `LLMSuggestionRejectionResult`: emits the rejection event capturing the proposal (classification/category/iva or split child_count) + operator reason, persisted through the transaction repository's secure-write batch (unchanged catalogue), mutating nothing.
- Re-export both from the package top level.

## Outcome

A rejection records a captured audit event and leaves the row unclassified; verified by 5 real-behaviour tests.

## Notes

Persisted via `_save_transaction_catalogue_and_events` (not a bare event-repo save) so the default CLI event repo binds to the active bucket, mirroring the apply path.

