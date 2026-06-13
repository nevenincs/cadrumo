---
tags:
  - '#exec'
  - '#llm-evidence-classification'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S03'
related:
  - "[[2026-06-13-llm-evidence-classification-plan]]"
---




# Test image evidence without --llm classifies via the vision model and text/no-evidence without --llm refuses instructively

## Scope

- `src/aeat/application/ledger/tests/test_llm_vision_evidence.py`

## Description

- Add tests: image evidence with no provider classifies via the vision model; text/no-evidence with no provider refuses instructively.

## Outcome

- Both real-behaviour tests pass (loopback Ollama + refusal). Committed `41c17af16`.

## Notes

