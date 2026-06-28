---
tags:
  - '#exec'
  - '#llm-classification-workflow'
date: '2026-06-14'
modified: '2026-06-15'
step_id: 'S02'
related:
  - "[[2026-06-14-llm-classification-workflow-plan]]"
---




# Add multiple_components to LLMClassificationResponse

## Scope

- `ask for it in the classification prompt when evidence is present`
- `src/aeat/domain/transactions/_llm.py`

## Description

- Add `multiple_components: bool | None` to `LLMClassificationResponse` (default None).
- Ask for it in the classification prompt only when evidence text or an image is present.

## Outcome

The classifier now reports invoice multiplicity from the evidence read; the parse path is unaffected (a boolean, not an allow-list value).

## Notes

None.

