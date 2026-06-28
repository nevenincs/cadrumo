---
tags:
  - '#exec'
  - '#cli-operator-surface'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S42'
related:
  - '[[2026-06-10-cli-operator-surface-plan]]'
---

# W03.P08.S42 Period Grammar Tests

Scope: verify real-behavior coverage for the strict ledger period grammar.

## Description

- Ran `test_ledger_period_grammar.py`.
- Confirmed coverage for accepted AEAT quarterly, annual, and monthly tokens with `--year`.
- Confirmed coverage for refused calendar shapes and combined year-qualified period forms.

## Outcome

S42 is closed. The focused real-behavior suite passed with 42 tests.

## Notes

- Checks run: `pytest src/aeat/entrypoints/cli/tests/test_ledger_period_grammar.py`.
