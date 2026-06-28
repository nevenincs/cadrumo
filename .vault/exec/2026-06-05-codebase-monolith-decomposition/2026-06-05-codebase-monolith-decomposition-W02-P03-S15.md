---
tags: ['#exec', '#codebase-monolith-decomposition']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S15'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W02.P03.S15 - modelo record extraction

Scope: `src/aeat/entrypoints/cli/_modelo.py` and `src/aeat/entrypoints/cli/_modelo_records_cli.py`.

## Description

- Added `_modelo_records_cli.py` as the focused registrar for filing-record and verification-report commands.
- Moved record/report Typer app creation, command bodies, output shaping, and service invocation out of `_modelo.py`.
- Replaced the removed `_modelo.py` command block with `register_record_commands(...)`.
- Preserved `_modelo.py` as the top-level facade for `filing_record_app`, `verification_report_app`, and the verification rendering helpers used by existing tests.

## Outcome

`_modelo.py` no longer owns filing-record or verification-report command bodies. The new module consumes application-layer modelo record/report services and the shared rendering helpers.

The root still owns work-amend parsing and delegates record import parsing through injected helper callables where the existing command contract needed shared validators.

## Notes

No fakes, mocks, monkeypatches, skips, or xfails were introduced.
