---
tags:
  - '#exec'
  - '#modelo-addressing-ux'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S70'
related:
  - '[[2026-06-04-modelo-addressing-ux-plan]]'
---

# `W04.P06.S70` Modelo 303 natural-key lifecycle rewrite

Step scope: `docs/how-to/modelo-303.md`.

## Description

- Validate the Modelo 303 how-to lifecycle path uses modelo, year, and period addressing.
- Confirm calculate, verify, export, status, and revisions examples avoid copied raw IDs.
- Preserve exact IDs as advanced recovery, automation, and ambiguity-resolution inputs.
- Verify educational-doc command and link conformance against the live CLI.

## Outcome

The Modelo 303 how-to is now a natural-key workflow. It creates, calculates, verifies, exports, checks status, and lists revisions using `--modelo 303 --year 2026 --period 1T`.

Verification passed with `.venv\Scripts\python.exe -m pytest -m docs src/aeat/entrypoints/cli/test_educational_docs_conformance.py`.

## Notes

An attempted `uv run pytest -m docs ...` failed because `uv` tried to reinstall `torch` and hit an access-denied error while renaming `c10.dll`. The existing virtualenv Python test invocation passed 29 tests.
