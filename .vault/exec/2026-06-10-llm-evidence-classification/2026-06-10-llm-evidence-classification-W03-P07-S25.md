---
tags:
  - '#exec'
  - '#llm-evidence-classification'
date: '2026-06-10'
modified: '2026-06-10'
step_id: 'S25'
related:
  - "[[2026-06-10-llm-evidence-classification-plan]]"
---




# Add an application path that validates children-sum-to-parent and sign invariants and drives split_transaction from a reviewed suggestion

## Scope

- `src/aeat/application/ledger/_llm_classification.py`

## Description

- Add `suggest_evidence_split`: loads the transaction, runs the resolved `LLMSplitProposer` over the optional on-host evidence text, derives each child's euro amount from the parent gross and the model's proportion via `derive_child_amounts` (summing exactly to the parent), and returns a typed `LLMSplitSuggestion`. Persists nothing.
- Add `apply_evidence_split`: composes the single-writer `split_transaction` (children-sum-to-parent + non-negative-magnitude invariants) from the reviewed suggestion, then per child composes `update_manual_transaction_fields`.

## Outcome

Commit `a9b654ed9`. The split path enforces children-sum-to-parent exactly; the per-child write enforces `gross == taxable_base + iva_amount`. Real-behaviour test `test_llm_evidence_split` (6 tests) green.

## Notes

Composes the established single writers rather than re-implementing them (`composition-service-no-parallel-write-path`).
