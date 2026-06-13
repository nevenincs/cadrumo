---
tags:
  - '#exec'
  - '#centralized-output-redaction'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S52'
related:
  - '[[2026-05-28-centralized-output-redaction-plan]]'
---


# W03.P09.S52 CLI surface redaction expectations

Scope: update the broad CLI surface tests so active bucket identifiers are asserted through centralized CLI output redaction.

## Description

- Replace hard-coded bucket placeholder expectations with the shared CLI redaction constant.
- Assert real parsed CLI JSON payloads do not contain the raw resolved active bucket id.
- Keep ledger transaction ids, event ids, and business fields visible where they are command-domain identifiers rather than profile bucket routing identifiers.

## Outcome

S52 is implemented for the current `test_cli_surface.py` surface.

## Notes

Focused ruff and pytest passed for `test_cli_surface.py`. No mocks, skips, xfails, or helper-only assertions were introduced.
