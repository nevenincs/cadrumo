---
tags:
  - '#exec'
  - '#llm-classification-workflow'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S07'
related:
  - "[[2026-06-14-llm-classification-workflow-plan]]"
---




# Add BucketEventType.LEDGER_TRANSACTION_LLM_SUGGESTION_REJECTED + catalogue pin test

## Scope

- `src/aeat/domain/buckets/_event.py`
- `src/aeat/domain/buckets/tests/test_event_catalogue.py`

## Description

- Add `BucketEventType.LEDGER_TRANSACTION_LLM_SUGGESTION_REJECTED` (`ledger.transaction.llm_suggestion.rejected`).
- Pin the value in the event-catalogue test.

## Outcome

The rejection event type exists and is catalogue-pinned.

## Notes

None.

