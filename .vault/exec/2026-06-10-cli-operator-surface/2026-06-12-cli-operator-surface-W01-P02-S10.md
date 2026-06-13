---
tags:
  - '#exec'
  - '#cli-operator-surface'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S10'
related:
  - '[[2026-06-10-cli-operator-surface-plan]]'
---

# W01.P02.S10 Preflight Help And Reference Gates

Scope: verify locale/help and generated reference state for the preflight signature.

## Description

- Verified English help for `config profile preflight` documents optional `--revision-id`.
- Verified `docs/cli/config.rst` documents the same optional override/default wording.
- Ran documented-command conformance and CLI-reference drift gates.

## Outcome

S10 is closed. Locale/help text and generated CLI reference match the natural-key preflight surface.

## Notes

- Checks run: `pytest src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py dev/docs/tests/test_cli_reference_drift.py`.
