---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-07-05'
modified: '2026-07-08'
step_id: 'S27'
related:
  - "[[2026-05-14-cli-workflow-redesign-modelo-145-reopen-plan]]"
---

# Validate Modelo 145 help text avoids file, filing, deadline, live-read, and AEAT submission vocabulary

## Scope

- `tests/entrypoints/cli`

## Description

- Ground `P05.S27` from the current plan status, semantic search for the M145 forbidden-surface vocabulary, and the existing M145 group-help coverage.
- Expand the M145 CLI help test from group-only coverage to every visible help surface: group, create, validate, export, mark-delivered-to-payer, and mark-locally-completed.
- Check forbidden help words and phrases for filing, deadline, live-read, portal, AEAT submission, submit, receipt, shim, stub, fake-support, deprecated-spelling, and compatibility-alias vocabulary.
- Keep the check token-aware so unrelated words such as `profile` do not create false failures.

## Outcome

- `P05.S27` implementation is complete and ready for plan-row closure.
- Verification passed:
  - Focused ruff check for the S27 M145 CLI integration test update: passed.
  - Focused ruff format check for the S27 M145 CLI integration test update: passed.
  - M145 real CLI integration slice, including all six help-surface vocabulary checks: 11 passed.

## Notes

- No production-code change was required; current M145 command help already uses local payer communication vocabulary.
- The code review found no blocking issues for `P05.S27`.
