---
tags:
  - '#exec'
  - '#llm-evidence-classification'
date: '2026-06-10'
step_id: 'S26'
related:
  - "[[2026-06-10-llm-evidence-classification-plan]]"
---




# Derive each child's regulated iva_rate, taxable_base, and iva_amount from the registry, never from the model

## Scope

- `src/aeat/application/ledger/_llm_classification.py`

## Description

- In `suggest_evidence_split`, derive each child's `iva_rate` / `taxable_base` / `iva_amount` via the shared `_derive_iva_substrate` from the model-selected `iva_category` and the child's derived gross — the same registry-rate + deterministic inverse-split path the saturate flow uses.
- In `apply_evidence_split`, persist those derived numbers per child through `update_manual_transaction_fields` only when the category is derivable.

## Outcome

Commit `a9b654ed9`. Test asserts each child's persisted `iva_rate == 0.21` (registry) and `taxable_base + iva_amount == child.amount`; the proposer supplies only proportions + categories, never a euro number (`llm-selects-system-derives-tax-numbers`).

## Notes

A non-derivable IVA category leaves the child numbers unset for the operator to complete, mirroring the saturate path.
