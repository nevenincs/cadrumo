---
tags:
  - '#exec'
  - '#llm-evidence-classification'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S02'
related:
  - "[[2026-06-13-llm-evidence-classification-plan]]"
---




# Route --read-evidence into the LLM path when --llm is absent

## Scope

- `refuse instructively when the text path needs a provider`
- `src/aeat/entrypoints/cli/_ledger.py`

## Description

- Route `--read-evidence` into the LLM path when `--llm` is absent; skip the provider-availability check when no provider is named.

## Outcome

- `classify --read-evidence` on a scanned/image invoice works with no provider; ty + 320 ledger tests green. Committed `41c17af16`.

## Notes

