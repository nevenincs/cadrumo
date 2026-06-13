---
tags:
  - '#exec'
  - '#llm-evidence-classification'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S36'
related:
  - "[[2026-06-10-llm-evidence-classification-plan]]"
---




# Roll classify --llm --saturate against a real cloud CLI

## Scope

- `confirm the model selects the IVA category`
- `the system derives rate/base/amount`
- `and the printed-vs-derived advisory behaves`
- `src/aeat/entrypoints/cli/_ledger.py`

## Description

- Run `app ledger classify <tx> --llm codex --saturate --read-evidence --evidence-acknowledged` and inspect the saturated preview, then `--apply`.

## Outcome

- The model selected IVA category `domestic_general_21`; the system DERIVED base 250.00, rate 0.21, IVA 52.50 (250.00 = 302.50 / 1.21 — registry-grounded, not model-emitted). The persisted transaction carries the derived regulated fields and `llm:codex` provenance. The printed-vs-derived figures agreed, so no advisory fired (expected — the invoice IVA matched the derived IVA). Captured in audit `2026-06-13-llm-evidence-classification-audit`.

## Notes

