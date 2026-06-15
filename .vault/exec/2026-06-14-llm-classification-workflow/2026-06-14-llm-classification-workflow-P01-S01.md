---
tags:
  - '#exec'
  - '#llm-classification-workflow'
date: '2026-06-14'
modified: '2026-06-15'
step_id: 'S01'
related:
  - "[[2026-06-14-llm-classification-workflow-plan]]"
---




# Relax LLMSplitResponse to >=1 child + recommends_split

## Scope

- `relax derive_child_amounts`
- `update build_split_prompt for the single-line verdict`
- `src/aeat/domain/transactions/_llm.py`
- `src/aeat/application/ledger/_evidence_split.py`

## Description

- Relax `LLMSplitResponse` to accept one-or-more children (was two-or-more); a single child at proportion 1.0 is the no-split verdict.
- Add `recommends_split` (more than one child) to `LLMSplitResponse`.
- Relax `derive_child_amounts` to accept one proportion, returning the whole gross on one child; reject only the empty case.
- Update `build_split_prompt` to ask for exactly one child for a single-line invoice, one per line otherwise.

## Outcome

Single-line invoices now have a first-class no-split verdict. `test_llm_split_schema.py` and `test_evidence_split.py` updated and green.

## Notes

The manual `split_transaction` still requires two-or-more children; only the LLM evidence-split derivation relaxed.

