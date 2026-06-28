---
tags:
  - '#exec'
  - '#llm-evidence-classification'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S35'
related:
  - "[[2026-06-10-llm-evidence-classification-plan]]"
---




# Roll classify --llm with a real cloud CLI (agy/codex) and --read-evidence --evidence-acknowledged

## Scope

- `confirm the model reads the invoice and the decision stamps llm provenance`
- `src/aeat/entrypoints/cli/_ledger.py`

## Description

- Run `app ledger classify <tx> --llm codex --saturate --read-evidence --evidence-acknowledged` against the real authenticated `codex` cloud CLI on the attached invoice.
- Re-run with `--apply` to persist the accepted suggestion.

## Outcome

- The model read the invoice (the bank row carried only "PAGO SUMINISTROS … 302.50"; the model returned base 250.00 / IVA 52.50, only knowable from the invoice) and classified BUSINESS / `hardware_amortizable`. `--apply` stamped `clasificado-por: llm:codex`, persisted the decision, set review status `reviewed`, and emitted a `ledger.transaction.classified` event. Provenance + evidence-read confirmed against the real model. Captured in audit `2026-06-13-llm-evidence-classification-audit`.

## Notes

