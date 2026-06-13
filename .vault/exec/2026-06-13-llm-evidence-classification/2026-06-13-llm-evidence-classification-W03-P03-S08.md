---
tags:
  - '#exec'
  - '#llm-evidence-classification'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S08'
related:
  - "[[2026-06-13-llm-evidence-classification-plan]]"
---




# Adversarially test parse_response: prompt-injection JSON, hostile/oversized output, out-of-allow-list values are rejected

## Scope

- `src/aeat/domain/transactions/tests/test_llm_parse_adversarial.py`

## Description

- Adversarially test `parse_response`: out-of-allow-list values, invalid enums, no-JSON, out-of-range confidence, oversized reason, and injected-prose-before-valid.

## Outcome

- 8 parser tests pass; the allow-list contains every hostile output. Committed `1572036a8`.

## Notes

