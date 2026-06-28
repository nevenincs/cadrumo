---
tags:
  - '#exec'
  - '#llm-evidence-classification'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S37'
related:
  - "[[2026-06-10-llm-evidence-classification-plan]]"
---




# Roll split --llm --read-evidence --apply against a real multi-line invoice with a real cloud CLI

## Scope

- `confirm children sum to parent`
- `registry-derived numbers`
- `evidence links`
- `and provenance`
- `src/aeat/entrypoints/cli/_ledger_lifecycle_cli.py`

## Description

- Build a two-line invoice (Portátil base 250 + IVA 52.50; Material base 100 + IVA 21) booked as one 423.50 transaction; `evidence add` + `attach`.
- Run `app ledger split <tx> --llm codex --read-evidence --evidence-acknowledged --apply --yes` against the real `codex` CLI.

## Outcome

- The model read the two-line invoice and produced a 2-child split: child 1 = 302.50 ("1. Linea 1: Portatil"), child 2 = 121.00 ("2. Linea 2: Material"); children sum exactly to the 423.50 parent. Descriptions carry the model's evidence citations; both children stamp `llm:codex`. The destructive-op `--yes` gate and the cloud-evidence consent gate both fired and were instructive. Captured in audit `2026-06-13-llm-evidence-classification-audit`.

## Notes

