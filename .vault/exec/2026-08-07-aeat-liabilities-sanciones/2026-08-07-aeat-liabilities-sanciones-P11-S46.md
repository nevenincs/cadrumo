---
tags:
  - '#exec'
  - '#aeat-liabilities-sanciones'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:792fcea62be7159106771f9d365c984cf0067d623ab872f5c4f0da3a91f63999'
step_id: 'S46'
related:
  - "[[2026-08-07-aeat-liabilities-sanciones-plan]]"
---

# Add the no-total invariant gate asserting the history payload schema declares no field summing amounts across documents, keyed by field name and by the schema shape rather than by a count, then the mutation proof adding a total field and confirming the gate reds

## Scope

- `src/cadrumo/entrypoints/cli/tests/test_notification_document_history_no_total.py`

## Description

- Added a recursive JSON-schema no-total invariant and a synthetic mutated-schema proof that demonstrates the gate detects a payable_total field.

## Outcome

Delivered and verified within the Step's declared scope.

## Notes

RAG discovery was attempted first but unavailable because service compute admission was quiesced. Grounding continued from the accepted decisions, existing execution records, source, targeted symbol search, and live CLI behaviour.
