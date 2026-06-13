---
tags:
  - '#exec'
  - '#modelo-addressing-ux'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S71'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# `W04.P06.S71` Modelo 390 natural-key lifecycle rewrite

Step scope: `docs/how-to/modelo-390.md`.

## Description

- Validate the annual Modelo 390 guide uses modelo, year, and period addressing.
- Confirm the guide checks quarterly Modelo 303 history through natural-key status commands.
- Confirm create, calculate, verify, and export examples avoid copied raw IDs.
- Verify educational-doc command and link conformance against the live CLI.

## Outcome

The Modelo 390 how-to now builds the annual summary by visible filing target with `--modelo 390 --year 2025 --period 0A`. It uses natural-key status checks for the prerequisite quarterly Modelo 303 filings and reserves exact IDs for advanced revision selection or automation.

Verification passed with `.venv\Scripts\python.exe -m pytest -m docs src/aeat/entrypoints/cli/test_educational_docs_conformance.py`.

## Notes

No additional source edit was needed during this step beyond persisting the already natural-key Modelo 390 guide and recording verification.
