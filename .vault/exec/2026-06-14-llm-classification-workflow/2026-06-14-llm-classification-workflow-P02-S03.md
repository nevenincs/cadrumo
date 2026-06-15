---
tags:
  - '#exec'
  - '#llm-classification-workflow'
date: '2026-06-14'
modified: '2026-06-15'
step_id: 'S03'
related:
  - "[[2026-06-14-llm-classification-workflow-plan]]"
---




# Carry multiple_components into LLMClassificationSuggestion + LLMSaturatedSuggestion

## Scope

- `add recommends_split`
- `add apply_evidence_classification`
- `guard apply_evidence_split`
- `src/aeat/application/ledger/_llm_classification.py`

## Description

- Carry `multiple_components` into `LLMClassificationSuggestion` and `LLMSaturatedSuggestion`, each exposing `recommends_split`.
- Add `apply_evidence_classification` to write a no-split (single-child) suggestion in place on the parent via the single-writer manual write.
- Guard `apply_evidence_split` to refuse a single-child no-split verdict.

## Outcome

The application layer routes a no-split verdict to in-place classification and refuses to apply a degenerate one-way split. Re-exported from the package top-level.

## Notes

`apply_evidence_classification` reuses `update_manual_transaction_fields`, the same single-writer the per-child split apply uses (composition-service-no-parallel-write-path).

