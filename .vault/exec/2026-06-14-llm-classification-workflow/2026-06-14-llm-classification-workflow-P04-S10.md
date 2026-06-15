---
tags:
  - '#exec'
  - '#llm-classification-workflow'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S10'
related:
  - "[[2026-06-14-llm-classification-workflow-plan]]"
---




# Real-behaviour tests for reject (event recorded, no mutation, history/view)

## Scope

- `locales`
- `how-to review-loop section`
- `src/aeat/application/ledger/tests`
- `src/aeat/entrypoints/cli/tests`
- `src/aeat/locales`
- `docs/how-to/classify-with-llm.md`

## Description

- Add 5 application reject tests (event recorded, no mutation, saturated/split capture, unknown/non-active refusals) and 3 CLI reject tests (records-event, reject/apply exclusivity, auto-split reject).
- Add reject locale keys via the aeat.locales CLI; document the four-terminal loop in the classify-with-llm how-to.

## Outcome

All reject tests green; locale parity/honesty and documented-command conformance clean.

## Notes

Tests are real-behaviour (real persistence, DI proposers, no mocks).

