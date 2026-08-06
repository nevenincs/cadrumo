---
tags:
  - '#exec'
  - '#llm-evidence-classification'
date: '2026-06-13'
modified: '2026-07-17'
body_hash: 'sha256:0f39480386d9c6ca4f97baa3e08438d367157228b97875c41deaed548496c6b1'
step_id: 'S06'
related:
  - "[[2026-06-13-llm-evidence-classification-plan]]"
---

# Generate adversarial fixture variants (prompt-injection invoice, malformed/empty PDF, multi-page, foreign-language)

## Scope

- `src/aeat/application/ledger/tests/_evidence_corpus/`

## Description

- Generate adversarial variants: prompt-injection invoice, foreign-language invoice, malformed PDF, empty PDF.

## Outcome

- Four synthetic_generated adversarial fixtures added with honest sidecars. Committed `1572036a8`.

## Notes
