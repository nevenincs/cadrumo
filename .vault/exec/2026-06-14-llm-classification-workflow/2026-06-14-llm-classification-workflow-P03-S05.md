---
tags:
  - '#exec'
  - '#llm-classification-workflow'
date: '2026-06-14'
modified: '2026-06-15'
step_id: 'S05'
related:
  - "[[2026-06-14-llm-classification-workflow-plan]]"
---




# Real-behaviour tests: no-split verdict, in-place apply, auto-split route, recommendation Notice

## Scope

- `src/aeat/application/ledger/tests`
- `src/aeat/entrypoints/cli/tests`

## Description

- Add no-split-verdict, in-place-apply, and multi-child-refusal tests to the evidence-split application suite.
- Add a CLI auto-split + recommendation-Notice integration test file (real CLI, real persistence, DI proposer; no mocks).

## Outcome

10 application split tests and 6 CLI auto-split tests green; 165 LLM/domain/CLI tests pass with no regressions.

## Notes

Tests live under domain tests/ folders per tests-live-under-domain-tests-folders.

